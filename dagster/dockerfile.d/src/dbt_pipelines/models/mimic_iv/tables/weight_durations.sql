{{ config(tags=['silver']) }}

-- 성인 ICU 환자의 체중을 시작/종료 시각 구간으로 변환한 Silver 모델.
-- chartevents에서 입실체중(admit, 226512)과 일일체중(daily, 224639)을 추출한다.
-- 첫 입실체중은 intime - 2시간을 시작으로 잡고, 각 구간의 endtime은 다음 측정 시작 시각
-- (없으면 outtime + 2시간)으로 채운다. intime이 첫 측정보다 빠르면 gap을 첫 체중으로 backfill한다.
-- 출처: mimic-code concepts/demographics/weight_durations.sql (BigQuery → Trino 포팅)

with wt_stg as (
    select
        c.stay_id,
        c.charttime,
        c.valuenum as weight,
        case
            when c.itemid = 226512 then 'admit'  -- admit wt
            else 'daily'  -- daily weight
        end as weight_type
    from {{ source('mimiciv', 'chartevents') }} as c
    where
        c.valuenum is not null
        and c.itemid in (
            226512,  -- admit wt
            224639  -- daily weight
        )
        and c.valuenum > 0
),

-- weight_type별로 charttime 오름차순 행번호 부여
wt_stg1 as (
    select
        stay_id,
        charttime,
        weight_type,
        weight,
        row_number() over (
            partition by stay_id, weight_type
            order by charttime
        ) as rn
    from wt_stg
    where weight is not null
),

-- 첫 입실체중의 charttime을 intime - 2시간으로 교체
wt_stg2 as (
    select
        wt_stg1.stay_id,
        ie.intime,
        ie.outtime,
        wt_stg1.weight_type,
        wt_stg1.weight,
        case
            when wt_stg1.weight_type = 'admit' and wt_stg1.rn = 1
                then ie.intime - interval '2' hour
            else wt_stg1.charttime
        end as starttime
    from wt_stg1
    inner join {{ source('mimiciv', 'icustays') }} as ie
        on wt_stg1.stay_id = ie.stay_id
),

wt_stg3 as (
    select
        stay_id,
        intime,
        outtime,
        starttime,
        weight,
        weight_type,
        coalesce(
            lead(starttime) over (
                partition by stay_id
                order by starttime
            ),
            outtime + interval '2' hour
        ) as endtime
    from wt_stg2
),

-- charted admit/daily 체중의 시작/종료 시각 테이블
wt1 as (
    select
        stay_id,
        starttime,
        weight,
        weight_type,
        coalesce(
            endtime,
            -- ICU 퇴실 시각을 마지막 체중 측정의 종료로 보정(2시간 fuzziness 포함)
            lead(starttime) over (
                partition by stay_id
                order by starttime
            ),
            outtime + interval '2' hour
        ) as endtime
    from wt_stg3
),

-- stay_id별 첫 starttime과 해당 체중을 한 행으로 반환
wt_first as (
    select
        wt1.stay_id,
        wt1.starttime,
        wt1.weight,
        wt1.weight_type,
        row_number() over (
            partition by wt1.stay_id
            order by wt1.starttime
        ) as rn
    from wt1
),

-- intime이 첫 일일체중보다 빠르면 입실 초반에 gap이 생긴다.
-- 이를 막기 위해 gap을 찾아 첫 체중으로 backfill한다.
wt_fix as (
    select
        ie.stay_id,
        -- 2시간 fuzziness 윈도우 적용
        wt.starttime as endtime,
        wt.weight,
        wt.weight_type,
        ie.intime - interval '2' hour as starttime
    from {{ source('mimiciv', 'icustays') }} as ie
    inner join wt_first as wt
        on
            ie.stay_id = wt.stay_id
            and wt.rn = 1
            and ie.intime < wt.starttime
)

-- backfill 행을 메인 체중 테이블에 합친다
select
    wt1.stay_id,
    wt1.starttime,
    wt1.endtime,
    wt1.weight,
    wt1.weight_type
from wt1
union all
select
    wt_fix.stay_id,
    wt_fix.starttime,
    wt_fix.endtime,
    wt_fix.weight,
    wt_fix.weight_type
from wt_fix
