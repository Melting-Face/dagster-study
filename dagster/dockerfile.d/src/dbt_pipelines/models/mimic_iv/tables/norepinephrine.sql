{{ config(tags=['silver']) }}

-- norepinephrine(노르에피네프린) 투여 용량·기간을 inputevents에서 추출한 Silver 모델.
-- 대부분 mcg/kg/min 단위이나 일부 mg/kg/min 행이 잘못 기록되어 있어 mcg/kg/min으로 환산한다.
-- itemid 221906으로 필터링한다.
-- 출처: mimic-code concepts/medication/norepinephrine.sql (BigQuery → Trino 포팅)

select
    stay_id,
    linkorderid,
    -- 두 행은 mg/kg/min... 나머지는 mcg/kg/min 단위
    -- mg/kg/min 행은 잘못 기록된 것으로, 모두 mcg/kg/min(= ug/kg/min)으로 환산
    amount as vaso_amount,
    starttime,
    endtime,
    case
        when rateuom = 'mg/kg/min' and patientweight = 1 then rate
        -- 아래 행은 완결성을 위해 작성했으나 실제 행에는 영향 없음
        when rateuom = 'mg/kg/min' then rate * 1000.0
        else rate
    end as vaso_rate
from {{ source('mimiciv', 'inputevents') }}
where itemid = 221906  -- norepinephrine(노르에피네프린)
