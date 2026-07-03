{{ config(tags=['silver']) }}

-- 산소 공급(oxygen delivery) 정보를 charttime 단위로 피벗한 Silver 모델.
-- chartevents에서 o2 flow(223834·227582 병합)·additional o2 flow(227287)와
-- 산소 공급 장치(226732, 한 시각 최대 4개)를 추출해 같은 subject_id·charttime을
-- 한 행으로 모은다. o2 flow 계열은 storetime 최신값 1건만 남긴다.
-- 출처: mimic-code concepts/measurement/oxygen_delivery.sql (BigQuery → Trino 포팅)

with ce_stg1 as (
    select
        ce.subject_id,
        ce.stay_id,
        ce.charttime,
        ce.value,
        ce.valuenum,
        ce.valueuom,
        ce.storetime,
        -- o2 flow 계열(223834·227582)을 단일 itemid(223834)로 병합
        case
            when ce.itemid in (223834, 227582) then 223834
            else ce.itemid
        end as itemid
    from {{ source('mimiciv', 'chartevents') }} as ce
    where
        ce.value is not null
        and ce.itemid in (
            223834,  -- o2 flow
            227582,  -- bipap o2 flow
            227287  -- additional o2 flow
        )
),

ce_stg2 as (
    select
        ce.subject_id,
        ce.stay_id,
        ce.charttime,
        ce.itemid,
        ce.value,
        ce.valuenum,
        ce.valueuom,
        -- charttime·itemid당 storetime 최신값 1건만 남기기 위한 순번
        row_number() over (
            partition by ce.subject_id, ce.charttime, ce.itemid
            order by ce.storetime desc
        ) as rn
    from ce_stg1 as ce
),

o2 as (
    -- 산소 공급 장치(226732)는 한 charttime에 여러 행(최대 4개) 존재 가능
    select
        ce.subject_id,
        ce.stay_id,
        ce.charttime,
        ce.itemid,
        ce.value as o2_device,
        row_number() over (
            partition by ce.subject_id, ce.charttime, ce.itemid
            order by ce.value
        ) as rn
    from {{ source('mimiciv', 'chartevents') }} as ce
    where ce.itemid = 226732  -- oxygen delivery device(s)
),

stg as (
    select
        ce.value,
        ce.valuenum,
        o2.o2_device,
        o2.rn,
        coalesce(ce.subject_id, o2.subject_id) as subject_id,
        coalesce(ce.stay_id, o2.stay_id) as stay_id,
        coalesce(ce.charttime, o2.charttime) as charttime,
        coalesce(ce.itemid, o2.itemid) as itemid
    from ce_stg2 as ce
    full outer join o2
        on
            ce.subject_id = o2.subject_id
            and ce.charttime = o2.charttime
    -- ce_stg2에서 subject_id·charttime·itemid당 1행으로 제한
    where ce.rn = 1
)

select
    subject_id,
    charttime,
    max(stay_id) as stay_id,
    max(case when itemid = 223834 then valuenum end) as o2_flow,
    max(case when itemid = 227287 then valuenum end) as o2_flow_additional,
    -- 환자의 모든 산소 공급 장치를 보존
    max(case when rn = 1 then o2_device end) as o2_delivery_device_1,
    max(case when rn = 2 then o2_device end) as o2_delivery_device_2,
    max(case when rn = 3 then o2_device end) as o2_delivery_device_3,
    max(case when rn = 4 then o2_device end) as o2_delivery_device_4
from stg
group by subject_id, charttime
