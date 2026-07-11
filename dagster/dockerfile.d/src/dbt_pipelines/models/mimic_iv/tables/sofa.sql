{{ config(tags=['silver']) }}

-- SOFA(Sequential Organ Failure Assessment) 점수를 ICU 재실 시간격자(매시간)로 계산하는 Silver 모델.
-- 6개 장기 시스템 점수를 산출한다:
--   respiration   : pao2/fio2 비율 + 침습환기 여부
--   coagulation   : 혈소판(platelet) 최소값
--   liver         : 빌리루빈(bilirubin) 최대값
--   cardiovascular: 평균동맥압(map) 최소값 + 승압제(dopamine·dobutamine·epinephrine·norepinephrine) 투여율
--   cns           : gcs 최소값
--   renal         : creatinine 최대값 + 소변량(urine output)
-- icustay_hourly로 매시간 행을 만들고 각 컴포넌트 점수를 산출한 뒤,
-- 24시간 롤링 윈도우(ROWS BETWEEN 23 PRECEDING AND 0 FOLLOWING)의 최대값으로 *_24hours 컬럼을 만들고
-- 6개 점수를 합산해 sofa_24hours(0~24)를 만든다.
-- 첫 24시간 구간은 데이터 윈도우가 불완전하므로 사용 시 주의가 필요하다.
-- 출처: mimic-code concepts/score/sofa.sql (BigQuery → Trino 포팅)

with co as (
    select
        ih.stay_id,
        ie.hadm_id,
        ih.hr,
        -- start/endtime으로 해당 시간 구간 내 값을 필터링
        ih.endtime,
        ih.endtime - interval '1' hour as starttime
    from {{ ref('icustay_hourly') }} as ih
    inner join {{ source('mimiciv', 'icustays') }} as ie
        on ih.stay_id = ie.stay_id
),

pafi as (
    -- 혈액가스를 환기 기간과 조인해 환자가 환기 중이었는지 판단
    select
        ie.stay_id,
        bg.charttime,
        -- pafi는 환기 여부와 pao2:fio2가 상호작용하므로 점수용으로 두 컬럼이 필요하다.
        -- 비환기 최저 pao2/fio2가 68, 환기 최저가 120일 수 있는데
        -- 이 경우 sofa 점수는 4가 아니라 3이다.
        case
            when vd.stay_id is null then bg.pao2fio2ratio
        end as pao2fio2ratio_novent,
        case
            when vd.stay_id is not null then bg.pao2fio2ratio
        end as pao2fio2ratio_vent
    from {{ source('mimiciv', 'icustays') }} as ie
    inner join {{ ref('bg') }} as bg
        on ie.subject_id = bg.subject_id
    left join {{ ref('ventilation') }} as vd
        on
            ie.stay_id = vd.stay_id
            and bg.charttime >= vd.starttime
            and bg.charttime <= vd.endtime
            and vd.ventilation_status = 'InvasiveVent'
    where bg.specimen = 'ART.'
),

vs as (
    select
        co.stay_id,
        co.hr,
        -- vitals
        min(vs.mbp) as meanbp_min
    from co
    left join {{ ref('vitalsign') }} as vs
        on
            co.stay_id = vs.stay_id
            and co.starttime < vs.charttime
            and co.endtime >= vs.charttime
    group by co.stay_id, co.hr
),

gcs as (
    select
        co.stay_id,
        co.hr,
        -- gcs
        min(gcs.gcs) as gcs_min
    from co
    left join {{ ref('gcs') }} as gcs
        on
            co.stay_id = gcs.stay_id
            and co.starttime < gcs.charttime
            and co.endtime >= gcs.charttime
    group by co.stay_id, co.hr
),

bili as (
    select
        co.stay_id,
        co.hr,
        max(enz.bilirubin_total) as bilirubin_max
    from co
    left join {{ ref('enzyme') }} as enz
        on
            co.hadm_id = enz.hadm_id
            and co.starttime < enz.charttime
            and co.endtime >= enz.charttime
    group by co.stay_id, co.hr
),

cr as (
    select
        co.stay_id,
        co.hr,
        max(chem.creatinine) as creatinine_max
    from co
    left join {{ ref('chemistry') }} as chem
        on
            co.hadm_id = chem.hadm_id
            and co.starttime < chem.charttime
            and co.endtime >= chem.charttime
    group by co.stay_id, co.hr
),

plt as (
    select
        co.stay_id,
        co.hr,
        min(cbc.platelet) as platelet_min
    from co
    left join {{ ref('complete_blood_count') }} as cbc
        on
            co.hadm_id = cbc.hadm_id
            and co.starttime < cbc.charttime
            and co.endtime >= cbc.charttime
    group by co.stay_id, co.hr
),

pf as (
    select
        co.stay_id,
        co.hr,
        min(pafi.pao2fio2ratio_novent) as pao2fio2ratio_novent,
        min(pafi.pao2fio2ratio_vent) as pao2fio2ratio_vent
    from co
    -- 해당 시간 구간에 발생한 혈액가스를 가져온다
    left join pafi
        on
            co.stay_id = pafi.stay_id
            and co.starttime < pafi.charttime
            and co.endtime >= pafi.charttime
    group by co.stay_id, co.hr
),

-- 값 중복을 막기 위해 uo는 별도로 합산
uo as (
    select
        co.stay_id,
        co.hr,
        -- uo: 22~30시간 구간 데이터를 24시간 기준으로 환산
        max(
            case
                when uo.uo_tm_24hr >= 22 and uo.uo_tm_24hr <= 30
                    then cast(uo.urineoutput_24hr as double) / uo.uo_tm_24hr * 24
            end
        ) as uo_24hr
    from co
    left join {{ ref('urine_output_rate') }} as uo
        on
            co.stay_id = uo.stay_id
            and co.starttime < uo.charttime
            and co.endtime >= uo.charttime
    group by co.stay_id, co.hr
),

-- 승압제를 시간당 1행으로 collapse, charttime당 1행만 보장
vaso as (
    select
        co.stay_id,
        co.hr,
        max(epi.vaso_rate) as rate_epinephrine,
        max(nor.vaso_rate) as rate_norepinephrine,
        max(dop.vaso_rate) as rate_dopamine,
        max(dob.vaso_rate) as rate_dobutamine
    from co
    left join {{ ref('epinephrine') }} as epi
        on
            co.stay_id = epi.stay_id
            and co.endtime > epi.starttime
            and co.endtime <= epi.endtime
    left join {{ ref('norepinephrine') }} as nor
        on
            co.stay_id = nor.stay_id
            and co.endtime > nor.starttime
            and co.endtime <= nor.endtime
    left join {{ ref('dopamine') }} as dop
        on
            co.stay_id = dop.stay_id
            and co.endtime > dop.starttime
            and co.endtime <= dop.endtime
    left join {{ ref('dobutamine') }} as dob
        on
            co.stay_id = dob.stay_id
            and co.endtime > dob.starttime
            and co.endtime <= dob.endtime
    where
        epi.stay_id is not null
        or nor.stay_id is not null
        or dop.stay_id is not null
        or dob.stay_id is not null
    group by co.stay_id, co.hr
),

scorecomp as (
    select
        co.stay_id,
        co.hr,
        co.starttime,
        co.endtime,
        pf.pao2fio2ratio_novent,
        pf.pao2fio2ratio_vent,
        vaso.rate_epinephrine,
        vaso.rate_norepinephrine,
        vaso.rate_dopamine,
        vaso.rate_dobutamine,
        vs.meanbp_min,
        gcs.gcs_min,
        -- uo
        uo.uo_24hr,
        -- labs
        bili.bilirubin_max,
        cr.creatinine_max,
        plt.platelet_min
    from co
    left join vs
        on
            co.stay_id = vs.stay_id
            and co.hr = vs.hr
    left join gcs
        on
            co.stay_id = gcs.stay_id
            and co.hr = gcs.hr
    left join bili
        on
            co.stay_id = bili.stay_id
            and co.hr = bili.hr
    left join cr
        on
            co.stay_id = cr.stay_id
            and co.hr = cr.hr
    left join plt
        on
            co.stay_id = plt.stay_id
            and co.hr = plt.hr
    left join pf
        on
            co.stay_id = pf.stay_id
            and co.hr = pf.hr
    left join uo
        on
            co.stay_id = uo.stay_id
            and co.hr = uo.hr
    left join vaso
        on
            co.stay_id = vaso.stay_id
            and co.hr = vaso.hr
),

scorecalc as (
    -- 최종 점수 계산.
    -- 원천 데이터가 없으면 컴포넌트는 null이 되고, 이후 0(정상)으로 처리되지만
    -- 결측 시점을 아는 것이 디버깅에 유용하므로 여기서는 null로 둔다.
    select
        scorecomp.*,
        -- Respiration
        case
            when scorecomp.pao2fio2ratio_vent < 100 then 4
            when scorecomp.pao2fio2ratio_vent < 200 then 3
            when scorecomp.pao2fio2ratio_novent < 300 then 2
            when scorecomp.pao2fio2ratio_vent < 300 then 2
            when scorecomp.pao2fio2ratio_novent < 400 then 1
            when scorecomp.pao2fio2ratio_vent < 400 then 1
            when
                coalesce(
                    scorecomp.pao2fio2ratio_vent, scorecomp.pao2fio2ratio_novent
                ) is null then null
            else 0
        end as respiration,
        -- Coagulation
        case
            when scorecomp.platelet_min < 20 then 4
            when scorecomp.platelet_min < 50 then 3
            when scorecomp.platelet_min < 100 then 2
            when scorecomp.platelet_min < 150 then 1
            when scorecomp.platelet_min is null then null
            else 0
        end as coagulation,
        -- Liver
        case
            -- 빌리루빈 단위 mg/dL
            when scorecomp.bilirubin_max >= 12.0 then 4
            when scorecomp.bilirubin_max >= 6.0 then 3
            when scorecomp.bilirubin_max >= 2.0 then 2
            when scorecomp.bilirubin_max >= 1.2 then 1
            when scorecomp.bilirubin_max is null then null
            else 0
        end as liver,
        -- Cardiovascular
        case
            when
                scorecomp.rate_dopamine > 15
                or scorecomp.rate_epinephrine > 0.1
                or scorecomp.rate_norepinephrine > 0.1
                then 4
            when
                scorecomp.rate_dopamine > 5
                or scorecomp.rate_epinephrine <= 0.1
                or scorecomp.rate_norepinephrine <= 0.1
                then 3
            when
                scorecomp.rate_dopamine > 0
                or scorecomp.rate_dobutamine > 0
                then 2
            when scorecomp.meanbp_min < 70 then 1
            when
                coalesce(
                    scorecomp.meanbp_min,
                    scorecomp.rate_dopamine,
                    scorecomp.rate_dobutamine,
                    scorecomp.rate_epinephrine,
                    scorecomp.rate_norepinephrine
                ) is null then null
            else 0
        end as cardiovascular,
        -- Neurological failure (GCS)
        case
            when (scorecomp.gcs_min >= 13 and scorecomp.gcs_min <= 14) then 1
            when (scorecomp.gcs_min >= 10 and scorecomp.gcs_min <= 12) then 2
            when (scorecomp.gcs_min >= 6 and scorecomp.gcs_min <= 9) then 3
            when scorecomp.gcs_min < 6 then 4
            when scorecomp.gcs_min is null then null
            else 0
        end as cns,
        -- Renal failure - 높은 creatinine 또는 낮은 소변량
        case
            when (scorecomp.creatinine_max >= 5.0) then 4
            when scorecomp.uo_24hr < 200 then 4
            when (scorecomp.creatinine_max >= 3.5 and scorecomp.creatinine_max < 5.0) then 3
            when scorecomp.uo_24hr < 500 then 3
            when (scorecomp.creatinine_max >= 2.0 and scorecomp.creatinine_max < 3.5) then 2
            when (scorecomp.creatinine_max >= 1.2 and scorecomp.creatinine_max < 2.0) then 1
            when coalesce(scorecomp.uo_24hr, scorecomp.creatinine_max) is null then null
            else 0
        end as renal
    from scorecomp
),

score_final as (
    select
        s.*,
        -- 모든 점수를 합쳐 SOFA 산출. 결측은 0으로 대체.
        -- 윈도우 함수가 최근 24시간의 최대값을 취한다.
        coalesce(
            max(s.respiration) over w, 0
        ) as respiration_24hours,
        coalesce(
            max(s.coagulation) over w, 0
        ) as coagulation_24hours,
        coalesce(
            max(s.liver) over w, 0
        ) as liver_24hours,
        coalesce(
            max(s.cardiovascular) over w, 0
        ) as cardiovascular_24hours,
        coalesce(
            max(s.cns) over w, 0
        ) as cns_24hours,
        coalesce(
            max(s.renal) over w, 0
        ) as renal_24hours,
        -- 최종 SOFA 합산
        coalesce(max(s.respiration) over w, 0)
        + coalesce(max(s.coagulation) over w, 0)
        + coalesce(max(s.liver) over w, 0)
        + coalesce(max(s.cardiovascular) over w, 0)
        + coalesce(max(s.cns) over w, 0)
        + coalesce(max(s.renal) over w, 0)
            as sofa_24hours
    from scorecalc as s
    window w as (
        partition by stay_id
        order by hr
        rows between 23 preceding and 0 following
    )
)

select * from score_final
where hr >= 0
