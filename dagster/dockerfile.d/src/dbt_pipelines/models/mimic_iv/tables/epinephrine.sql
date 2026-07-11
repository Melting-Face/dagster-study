{{ config(tags=['silver']) }}

-- epinephrine(에피네프린) 투여 용량·기간을 inputevents에서 추출한 Silver 모델.
-- 모든 행이 mcg/kg/min 단위이며, itemid 221289로 필터링한다.
-- 출처: mimic-code concepts/medication/epinephrine.sql (BigQuery → Trino 포팅)

select
    stay_id,
    linkorderid,
    -- 모든 행 mcg/kg/min 단위
    rate as vaso_rate,
    amount as vaso_amount,
    starttime,
    endtime
from {{ source('mimiciv', 'inputevents') }}
where itemid = 221289  -- epinephrine(에피네프린)
