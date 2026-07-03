{{ config(tags=['silver']) }}

-- 전혈구계산(CBC) 검사값을 specimen_id 단위로 피벗한 Silver 모델.
-- labevents에서 적혈구용적(hematocrit)·혈색소(hemoglobin)·MCH/MCHC/MCV·혈소판·RBC·RDW·WBC
-- 관련 itemid를 추출하고, 같은 검체(specimen_id)를 한 행으로 모은다.
-- 검사값은 0·음수일 수 없으므로 valuenum > 0 조건으로 필터링한다.
-- 출처: mimic-code concepts/measurement/complete_blood_count.sql (BigQuery → Trino 포팅)

select
    le.specimen_id,
    max(le.subject_id) as subject_id,
    max(le.hadm_id) as hadm_id,
    max(le.charttime) as charttime,
    max(case when le.itemid = 51221 then le.valuenum end) as hematocrit,  -- 적혈구용적
    max(case when le.itemid = 51222 then le.valuenum end) as hemoglobin,  -- 혈색소
    max(case when le.itemid = 51248 then le.valuenum end) as mch,  -- 평균적혈구혈색소량
    max(case when le.itemid = 51249 then le.valuenum end) as mchc,  -- 평균적혈구혈색소농도
    max(case when le.itemid = 51250 then le.valuenum end) as mcv,  -- 평균적혈구용적
    max(case when le.itemid = 51265 then le.valuenum end) as platelet,  -- 혈소판
    max(case when le.itemid = 51279 then le.valuenum end) as rbc,  -- 적혈구수
    max(case when le.itemid = 51277 then le.valuenum end) as rdw,  -- 적혈구분포폭
    max(case when le.itemid = 52159 then le.valuenum end) as rdwsd,  -- 적혈구분포폭(표준편차)
    max(case when le.itemid = 51301 then le.valuenum end) as wbc  -- 백혈구수
from {{ source('mimiciv', 'labevents') }} as le
where
    le.itemid in (
        51221,  -- hematocrit
        51222,  -- hemoglobin
        51248,  -- mch
        51249,  -- mchc
        51250,  -- mcv
        51265,  -- platelets
        51279,  -- rbc
        51277,  -- rdw
        52159,  -- rdw sd
        51301  -- wbc
    )
    and le.valuenum is not null
    -- 검사값은 0·음수일 수 없음
    and le.valuenum > 0
group by le.specimen_id
