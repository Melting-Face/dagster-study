{{ config(tags=['silver']) }}

-- 혈액 화학 검사(chemistry) 결과를 specimen_id 단위로 피벗한 Silver 모델.
-- labevents에서 알부민·글로불린·총단백·anion gap·중탄산염·BUN·칼슘·염소·크레아티닌·
-- 포도당·나트륨·칼륨 관련 itemid를 추출하고, 같은 specimen_id를 한 행으로 모은다.
-- 동맥혈가스(bg)와 현장검사(point of care)는 제외한다.
-- 검사값은 0·음수 불가(anion gap 50868만 예외)이며, itemid별 상한 범위 밖은 null 처리한다.
-- 출처: mimic-code concepts/measurement/chemistry.sql (BigQuery → Trino 포팅)

select
    le.specimen_id,
    max(le.subject_id) as subject_id,
    max(le.hadm_id) as hadm_id,
    max(le.charttime) as charttime,
    max(case when le.itemid = 50862 and le.valuenum <= 10 then le.valuenum end) as albumin,  -- 알부민
    -- 글로불린
    max(case when le.itemid = 50930 and le.valuenum <= 10 then le.valuenum end) as globulin,
    -- 총단백
    max(case when le.itemid = 50976 and le.valuenum <= 20 then le.valuenum end) as total_protein,
    -- anion gap
    max(case when le.itemid = 50868 and le.valuenum <= 10000 then le.valuenum end) as aniongap,
    -- 중탄산염
    max(case when le.itemid = 50882 and le.valuenum <= 10000 then le.valuenum end) as bicarbonate,
    -- 혈중요소질소(BUN)
    max(case when le.itemid = 51006 and le.valuenum <= 300 then le.valuenum end) as bun,
    -- 칼슘
    max(case when le.itemid = 50893 and le.valuenum <= 10000 then le.valuenum end) as calcium,
    -- 염소
    max(case when le.itemid = 50902 and le.valuenum <= 10000 then le.valuenum end) as chloride,
    -- 크레아티닌
    max(case when le.itemid = 50912 and le.valuenum <= 150 then le.valuenum end) as creatinine,
    -- 포도당
    max(case when le.itemid = 50931 and le.valuenum <= 10000 then le.valuenum end) as glucose,
    max(case when le.itemid = 50983 and le.valuenum <= 200 then le.valuenum end) as sodium,  -- 나트륨
    max(case when le.itemid = 50971 and le.valuenum <= 30 then le.valuenum end) as potassium  -- 칼륨
from {{ source('mimiciv', 'labevents') }} as le
where
    le.itemid in (
        50862,  -- albumin
        50930,  -- globulin
        50976,  -- total protein
        50868,  -- anion gap
        50882,  -- bicarbonate
        50893,  -- calcium
        50912,  -- creatinine
        50902,  -- chloride
        50931,  -- glucose
        50971,  -- potassium
        50983,  -- sodium
        51006  -- urea nitrogen (BUN)
    )
    and le.valuenum is not null
    -- 검사값은 0·음수 불가, 단 anion gap(50868)은 예외
    and (le.valuenum > 0 or le.itemid = 50868)
group by le.specimen_id
