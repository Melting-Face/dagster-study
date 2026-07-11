{{ config(tags=['silver']) }}

-- 간·심장 효소 검사값(labevents)을 specimen_id 단위로 피벗한 Silver 모델.
-- ALT·ALP·AST·Amylase·총/직접/간접 빌리루빈·CK-CPK·CK-MB·GGT·LD(LDH) itemid를 추출하고,
-- 같은 specimen_id를 한 행으로 모은다.
-- 검사값은 0 이하일 수 없으므로 valuenum > 0 조건으로 비정상치를 제거한다.
-- 출처: mimic-code concepts/measurement/enzyme.sql (BigQuery → Trino 포팅)

select
    le.specimen_id,
    max(le.subject_id) as subject_id,
    max(le.hadm_id) as hadm_id,
    max(le.charttime) as charttime,
    max(case when le.itemid = 50861 then le.valuenum end) as alt,  -- alanine transaminase (alt)
    max(case when le.itemid = 50863 then le.valuenum end) as alp,  -- alkaline phosphatase (alp)
    max(case when le.itemid = 50878 then le.valuenum end) as ast,  -- aspartate transaminase (ast)
    max(case when le.itemid = 50867 then le.valuenum end) as amylase,  -- amylase
    max(case when le.itemid = 50885 then le.valuenum end) as bilirubin_total,  -- total bili
    max(case when le.itemid = 50883 then le.valuenum end) as bilirubin_direct,  -- direct bili
    max(case when le.itemid = 50884 then le.valuenum end) as bilirubin_indirect,  -- indirect bili
    max(case when le.itemid = 50910 then le.valuenum end) as ck_cpk,  -- ck_cpk
    max(case when le.itemid = 50911 then le.valuenum end) as ck_mb,  -- ck-mb
    -- gamma glutamyltransferase (ggt)
    max(case when le.itemid = 50927 then le.valuenum end) as ggt,
    max(case when le.itemid = 50954 then le.valuenum end) as ld_ldh  -- ld_ldh
from {{ source('mimiciv', 'labevents') }} as le
where
    le.itemid in (
        50861,  -- alanine transaminase (alt)
        50863,  -- alkaline phosphatase (alp)
        50878,  -- aspartate transaminase (ast)
        50867,  -- amylase
        50885,  -- total bili
        50884,  -- indirect bili
        50883,  -- direct bili
        50910,  -- ck_cpk
        50911,  -- ck-mb
        50927,  -- gamma glutamyltransferase (ggt)
        50954  -- ld_ldh
    )
    and le.valuenum is not null
    -- 검사값은 0이거나 음수일 수 없음
    and le.valuenum > 0
group by le.specimen_id
