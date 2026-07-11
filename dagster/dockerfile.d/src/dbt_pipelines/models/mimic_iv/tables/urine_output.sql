{{ config(tags=['silver']) }}

-- 소변 배출량(urine output)을 stay_id·charttime 단위로 합산한 Silver 모델.
-- outputevents에서 Foley·Void·Condom Cath 등 소변 관련 itemid를 추출한다.
-- GU 관주액 주입(227488, GU Irrigant Volume In)은 음수 볼륨으로 처리해
-- 관주액 배출과 상쇄(net 0)되도록 한다.
-- 출처: mimic-code concepts/measurement/urine_output.sql (BigQuery → Trino 포팅)

with uo as (
    select
        oe.stay_id,
        oe.charttime,
        -- GU 관주액 주입은 음수 볼륨으로 환산(배출과 상쇄)
        case
            when oe.itemid = 227488 and oe.value > 0 then -1 * oe.value
            else oe.value
        end as urineoutput
    from {{ source('mimiciv', 'outputevents') }} as oe
    where oe.itemid in (
        226559,  -- foley
        226560,  -- void
        226561,  -- condom cath
        226584,  -- ileoconduit
        226563,  -- suprapubic
        226564,  -- r nephrostomy
        226565,  -- l nephrostomy
        226567,  -- straight cath
        226557,  -- r ureteral stent
        226558,  -- l ureteral stent
        227488,  -- gu irrigant volume in
        227489  -- gu irrigant/urine volume out
    )
)

select
    stay_id,
    charttime,
    sum(urineoutput) as urineoutput
from uo
group by stay_id, charttime
