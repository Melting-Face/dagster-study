{{ config(tags=['silver']) }}

-- 항생제 처방과 미생물 배양 검사를 시간 근접성으로 매칭해 감염 의심(suspicion of infection)을 판정하는 Silver 모델.
-- 배양 후 72시간 이내 항생제(me_then_ab) 또는 항생제 전 24시간 이내 배양(ab_then_me)을 연결한다.
-- 환자 1명의 동일 입원 내 모든 처방이 ICU stay마다 중복되며, ab_id로 항생제별 단일 배양 매칭을 보장한다.
-- charttime이 없으면 chartdate로 폴백한다.
-- 출처: mimic-code concepts/sepsis/suspicion_of_infection.sql (BigQuery → Trino 포팅)

with ab_tbl as (
    select
        abx.subject_id,
        abx.hadm_id,
        abx.stay_id,
        abx.antibiotic,
        abx.starttime as antibiotic_time,
        -- date는 charttime 없이 chartdate만 있는 배양과 매칭할 때 사용
        abx.stoptime as antibiotic_stoptime,
        date_trunc('day', abx.starttime) as antibiotic_date,
        -- 환자별 항생제 고유 식별자 생성
        row_number() over (
            partition by abx.subject_id
            order by abx.starttime, abx.stoptime, abx.antibiotic
        ) as ab_id
    from {{ ref('antibiotic') }} as abx
),

me as (
    select
        micro_specimen_id,
        -- 아래 컬럼들은 같은 micro_specimen_id 내에서 동일하므로 집계로 중복 제거
        cast(max(chartdate) as date) as chartdate,
        max(subject_id) as subject_id,
        max(hadm_id) as hadm_id,
        max(charttime) as charttime,
        max(spec_type_desc) as spec_type_desc,
        -- 음성 배양은 organism이 null 이거나 itemid 90856("NEGATIVE")으로 식별
        max(
            case
                when
                    org_name is not null
                    and org_itemid != 90856
                    and org_name != ''
                    then 1
                else 0
            end
        ) as positiveculture
    from {{ source('mimiciv', 'microbiologyevents') }}
    group by micro_specimen_id
),

-- 배양 후 항생제
me_then_ab as (
    select
        ab_tbl.subject_id,
        ab_tbl.hadm_id,
        ab_tbl.stay_id,
        ab_tbl.ab_id,
        me72.micro_specimen_id,
        me72.positiveculture as last72_positiveculture,
        me72.spec_type_desc as last72_specimen,
        coalesce(me72.charttime, cast(me72.chartdate as timestamp)) as last72_charttime,
        -- 이 항생제 직전의 가장 이른 배양을 선택하기 위한 파티션 (항생제당 단일 배양 보장)
        row_number() over (
            partition by ab_tbl.subject_id, ab_tbl.ab_id
            order by me72.chartdate, me72.charttime nulls last
        ) as micro_seq
    from ab_tbl
    -- 배양 이후 72시간 이내에 투여된 항생제
    left join me as me72
        on
            ab_tbl.subject_id = me72.subject_id
            and (
                (
                    -- charttime이 있으면 charttime 사용
                    me72.charttime is not null
                    and ab_tbl.antibiotic_time > me72.charttime
                    and ab_tbl.antibiotic_time <= me72.charttime + interval '72' hour
                )
                or (
                    -- charttime이 없으면 chartdate 사용
                    me72.charttime is null
                    and ab_tbl.antibiotic_date >= me72.chartdate
                    and ab_tbl.antibiotic_date <= me72.chartdate + interval '3' day
                )
            )
),

ab_then_me as (
    select
        ab_tbl.subject_id,
        ab_tbl.hadm_id,
        ab_tbl.stay_id,
        ab_tbl.ab_id,
        me24.micro_specimen_id,
        me24.positiveculture as next24_positiveculture,
        me24.spec_type_desc as next24_specimen,
        coalesce(me24.charttime, cast(me24.chartdate as timestamp)) as next24_charttime,
        -- 이 항생제 직후의 가장 이른 배양을 선택하기 위한 파티션 (항생제당 단일 배양 보장)
        row_number() over (
            partition by ab_tbl.subject_id, ab_tbl.ab_id
            order by me24.chartdate, me24.charttime nulls last
        ) as micro_seq
    from ab_tbl
    -- 이후 24시간 이내의 배양
    left join me as me24
        on
            ab_tbl.subject_id = me24.subject_id
            and (
                (
                    -- charttime이 있으면 charttime 사용
                    me24.charttime is not null
                    and ab_tbl.antibiotic_time >= me24.charttime - interval '24' hour
                    and ab_tbl.antibiotic_time < me24.charttime
                )
                or (
                    -- charttime이 없으면 chartdate 사용
                    me24.charttime is null
                    and ab_tbl.antibiotic_date >= me24.chartdate - interval '1' day
                    and ab_tbl.antibiotic_date <= me24.chartdate
                )
            )
)

select
    ab_tbl.subject_id,
    ab_tbl.stay_id,
    ab_tbl.hadm_id,
    ab_tbl.ab_id,
    ab_tbl.antibiotic,
    ab_tbl.antibiotic_time,
    case
        when me2ab.last72_specimen is null and ab2me.next24_specimen is null
            then 0
        else 1
    end as suspected_infection,
    -- 감염 의심 시각:
    --    (1) 배양 시각 (항생제보다 먼저인 경우)
    --    (2) 또는 항생제 시각 (배양보다 먼저인 경우)
    case
        when me2ab.last72_specimen is null and ab2me.next24_specimen is null
            then null
        else coalesce(me2ab.last72_charttime, ab_tbl.antibiotic_time)
    end as suspected_infection_time,
    coalesce(me2ab.last72_charttime, ab2me.next24_charttime) as culture_time,
    -- 배양된 검체
    coalesce(me2ab.last72_specimen, ab2me.next24_specimen) as specimen,
    -- 배양 검체의 양성 여부
    coalesce(
        me2ab.last72_positiveculture, ab2me.next24_positiveculture
    ) as positive_culture
from ab_tbl
left join ab_then_me as ab2me
    on
        ab_tbl.subject_id = ab2me.subject_id
        and ab_tbl.ab_id = ab2me.ab_id
        and ab2me.micro_seq = 1
left join me_then_ab as me2ab
    on
        ab_tbl.subject_id = me2ab.subject_id
        and ab_tbl.ab_id = me2ab.ab_id
        and me2ab.micro_seq = 1
