{{ config(tags=['silver']) }}

-- ICU stay별 첫·마지막 심박수(itemid 220045) 기록 시각 = fuzzy intime/outtime.
-- 공식 mimiciv_derived.icustay_times 포팅. icustay_hourly(시간 격자)의 입력.
-- 출처: mimic-code concepts/demographics/icustay_times.sql

with t1 as (
    select
        ce.stay_id,
        min(ce.charttime) as intime_hr,
        max(ce.charttime) as outtime_hr
    from {{ source('mimiciv', 'chartevents') }} as ce
    where ce.itemid = 220045  -- heart rate
    group by ce.stay_id
)

select
    ie.subject_id,
    ie.hadm_id,
    ie.stay_id,
    t1.intime_hr,
    t1.outtime_hr
from {{ source('mimiciv', 'icustays') }} as ie
left join t1
    on ie.stay_id = t1.stay_id
