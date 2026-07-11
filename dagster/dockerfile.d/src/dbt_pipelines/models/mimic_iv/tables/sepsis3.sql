{{ config(tags=['silver']) }}

-- ICU 내 Sepsis-3 발현(onset) 시각을 산출하는 Silver 모델.
-- SOFA >= 2 이면서 감염 의심(suspected_infection)이 있는 가장 이른 시점으로 정의한다.
-- (ICU 입실 전 baseline SOFA = 0 가정). 감염 의심 시각 기준 -48h ~ +24h 윈도우 안의
-- SOFA 행과 결합하고, stay_id별 가장 이른 감염 의심 1건만 남긴다.
-- 출처: mimic-code concepts/sepsis/sepsis3.sql (BigQuery → Trino 포팅)

with sofa as (
    select
        stay_id,
        starttime,
        endtime,
        respiration_24hours as respiration,
        coagulation_24hours as coagulation,
        liver_24hours as liver,
        cardiovascular_24hours as cardiovascular,
        cns_24hours as cns,
        renal_24hours as renal,
        sofa_24hours as sofa_score
    from {{ ref('sofa') }}
    where sofa_24hours >= 2
),

s1 as (
    select
        soi.subject_id,
        soi.stay_id,
        soi.ab_id,
        soi.antibiotic,
        soi.antibiotic_time,
        soi.culture_time,
        soi.suspected_infection,
        soi.suspected_infection_time,
        soi.specimen,
        soi.positive_culture,
        sofa.starttime,
        sofa.endtime,
        sofa.respiration,
        sofa.coagulation,
        sofa.liver,
        sofa.cardiovascular,
        sofa.cns,
        sofa.renal,
        sofa.sofa_score,
        sofa.sofa_score >= 2 and soi.suspected_infection = 1 as sepsis3,
        row_number() over (
            partition by soi.stay_id
            order by
                soi.suspected_infection_time,
                soi.antibiotic_time,
                soi.culture_time,
                sofa.endtime
        ) as rn_sus
    from {{ ref('suspicion_of_infection') }} as soi
    inner join sofa
        on
            soi.stay_id = sofa.stay_id
            -- 감염 의심 시각 기준 -48시간 ~ +24시간 윈도우 안의 SOFA 행과 결합
            and sofa.endtime >= soi.suspected_infection_time - interval '48' hour
            and sofa.endtime <= soi.suspected_infection_time + interval '24' hour
    where soi.stay_id is not null
)

select
    subject_id,
    stay_id,
    antibiotic_time,
    culture_time,
    suspected_infection_time,
    endtime as sofa_time,
    sofa_score,
    respiration,
    coagulation,
    liver,
    cardiovascular,
    cns,
    renal,
    sepsis3
from s1
where rn_sus = 1
