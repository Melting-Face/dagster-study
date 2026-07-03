{{ config(tags=['silver']) }}

-- 동맥/정맥 혈액가스(blood gas) 검사를 specimen_id 단위로 피벗한 Silver 모델.
-- labevents에서 pH·pCO2·pO2·FiO2·lactate·glucose·전해질 등 혈액가스 itemid를 추출해
-- specimen_id별로 한 행으로 모으고, chartevents의 spo2(2시간 이내)·fio2(4시간 이내)를 결합한다.
-- fio2(50816)는 20 이하 비생리적 값을 비율 오입력으로 보고 0.2~1.0 구간을 %로 환산한다.
-- 산소화 지표 aado2_calc(폐포-동맥 산소분압차)와 pao2fio2ratio(P/F비)를 함께 계산한다.
-- 출처: mimic-code concepts/measurement/bg.sql (BigQuery → Trino 포팅)

with bg as (
    select
        -- specimen_id는 itemid별로 측정이 1건이므로 max()로 단순 collapse 가능
        le.specimen_id,
        max(subject_id) as subject_id,
        max(hadm_id) as hadm_id,
        -- specimen_id가 서로 다른 storetime을 가질 수 있어 가장 최신값 사용
        max(charttime) as charttime,
        max(storetime) as storetime,
        max(case when le.itemid = 52033 then le.value end) as specimen,  -- 검체 종류
        max(case when le.itemid = 50801 then le.valuenum end) as aado2,  -- 폐포-동맥 산소분압차
        max(case when le.itemid = 50802 then le.valuenum end) as baseexcess,  -- 염기과잉
        max(case when le.itemid = 50803 then le.valuenum end) as bicarbonate,  -- 중탄산염
        max(case when le.itemid = 50804 then le.valuenum end) as totalco2,  -- 총 co2
        max(case when le.itemid = 50805 then le.valuenum end) as carboxyhemoglobin,  -- 카르복시헤모글로빈
        max(case when le.itemid = 50806 then le.valuenum end) as chloride,  -- 염소
        max(case when le.itemid = 50808 then le.valuenum end) as calcium,  -- 유리 칼슘
        max(
            case
                when le.itemid = 50809 and le.valuenum <= 10000 then le.valuenum
            end
        ) as glucose,  -- 혈당 (10000 초과 제거)
        max(
            case
                when le.itemid = 50810 and le.valuenum <= 100 then le.valuenum
            end
        ) as hematocrit,  -- 헤마토크릿 (100 초과 제거)
        max(case when le.itemid = 50811 then le.valuenum end) as hemoglobin,  -- 헤모글로빈
        max(
            case
                when le.itemid = 50813 and le.valuenum <= 10000 then le.valuenum
            end
        ) as lactate,  -- 젖산 (10000 초과 제거)
        max(case when le.itemid = 50814 then le.valuenum end) as methemoglobin,  -- 메트헤모글로빈
        max(case when le.itemid = 50815 then le.valuenum end) as o2flow,  -- 산소 유량
        -- fio2 단위 보정: 대기 중 o2는 20.89%라 20 이하 값은 비생리적(주로 o2 flow 오입력)
        max(case
            when le.itemid = 50816 then
                case
                    when le.valuenum > 20 and le.valuenum <= 100 then le.valuenum
                    when le.valuenum > 0.2 and le.valuenum <= 1.0 then le.valuenum * 100.0
                end
        end) as fio2,  -- 흡입 산소 분율
        max(
            case
                when le.itemid = 50817 and le.valuenum <= 100 then le.valuenum
            end
        ) as so2,  -- 산소 포화도 (100 초과 제거)
        max(case when le.itemid = 50818 then le.valuenum end) as pco2,  -- 이산화탄소 분압
        max(case when le.itemid = 50819 then le.valuenum end) as peep,  -- 호기말 양압
        max(case when le.itemid = 50820 then le.valuenum end) as ph,  -- 산도
        max(case when le.itemid = 50821 then le.valuenum end) as po2,  -- 산소 분압
        max(case when le.itemid = 50822 then le.valuenum end) as potassium,  -- 칼륨
        max(case when le.itemid = 50823 then le.valuenum end) as requiredo2,  -- 필요 산소
        max(case when le.itemid = 50824 then le.valuenum end) as sodium,  -- 나트륨
        max(case when le.itemid = 50825 then le.valuenum end) as temperature,  -- 체온
        max(case when le.itemid = 50807 then le.value end) as comments  -- 코멘트
    from {{ source('mimiciv', 'labevents') }} as le
    where
        le.itemid in (
            52033,  -- specimen 검체
            50801,  -- aado2
            50802,  -- base excess 염기과잉
            50803,  -- bicarb 중탄산
            50804,  -- calc tot co2 총 co2
            50805,  -- carboxyhgb
            50806,  -- chloride 염소
            50807,  -- comments
            50808,  -- free calcium 유리 칼슘
            50809,  -- glucose 혈당
            50810,  -- hct 헤마토크릿
            50811,  -- hgb 헤모글로빈
            50813,  -- lactate 젖산
            50814,  -- methemoglobin
            50815,  -- o2 flow 산소 유량
            50816,  -- fio2
            50817,  -- o2 sat 산소 포화도
            50818,  -- pco2
            50819,  -- peep
            50820,  -- ph
            50821,  -- po2
            50822,  -- potassium 칼륨
            50823,  -- required o2
            50824,  -- sodium 나트륨
            50825  -- temperature 체온
        )
    group by le.specimen_id
),

stg_spo2 as (
    select
        subject_id,
        charttime,
        -- avg는 charttime 단위로 spo2를 묶기 위한 용도
        avg(valuenum) as spo2
    from {{ source('mimiciv', 'chartevents') }}
    where
        itemid = 220277  -- 맥박산소측정 spo2
        and valuenum > 0
        and valuenum <= 100
    group by subject_id, charttime
),

stg_fio2 as (
    select
        subject_id,
        charttime,
        -- fio2를 21~100% 범위로 사전 정제
        max(
            case
                when valuenum > 0.2 and valuenum <= 1
                    then valuenum * 100  -- 비율값을 %로 환산
                when valuenum > 1 and valuenum < 20
                    then null  -- o2 flow(L) 오입력으로 보고 제거
                when valuenum >= 20 and valuenum <= 100
                    then valuenum
            end
        ) as fio2_chartevents
    from {{ source('mimiciv', 'chartevents') }}
    where
        itemid = 223835  -- 흡입 산소 분율 fio2
        and valuenum > 0
        and valuenum <= 100
    group by subject_id, charttime
),

stg2 as (
    select
        bg.*,
        s1.spo2,
        row_number() over (
            partition by bg.subject_id, bg.charttime
            order by s1.charttime desc
        ) as lastrowspo2
    from bg
    left join stg_spo2 as s1
        -- spo2가 혈액가스 채취 2시간 이내(이전)에 측정된 경우
        on
            bg.subject_id = s1.subject_id
            and s1.charttime
            between bg.charttime - interval '2' hour
            and bg.charttime
    where bg.po2 is not null
),

stg3 as (
    select
        bg.*,
        s2.fio2_chartevents,
        row_number() over (
            partition by bg.subject_id, bg.charttime
            order by s2.charttime desc
        ) as lastrowfio2
    from stg2 as bg
    left join stg_fio2 as s2
        -- fio2가 혈액가스 채취 4시간 이내(이전)에 측정된 경우
        on
            bg.subject_id = s2.subject_id
            and s2.charttime >= bg.charttime - interval '4' hour
            and bg.charttime >= s2.charttime
            and s2.fio2_chartevents > 0
    -- spo2가 가장 최근인 행만 (spo2 없으면 lastrowspo2 = 1)
    where bg.lastrowspo2 = 1
)

select
    stg3.subject_id,
    stg3.hadm_id,
    stg3.charttime,
    stg3.specimen,  -- 검체 종류 텍스트

    -- 산소 관련 지표
    stg3.so2,
    stg3.po2,
    stg3.pco2,
    stg3.fio2_chartevents,
    stg3.fio2,
    stg3.aado2,
    -- aado2(폐포-동맥 산소분압차) 직접 계산
    stg3.ph,
    stg3.baseexcess,
    -- 산-염기 지표
    stg3.bicarbonate,
    stg3.totalco2,
    stg3.hematocrit,
    stg3.hemoglobin,

    -- 혈구 지표
    stg3.carboxyhemoglobin,
    stg3.methemoglobin,
    stg3.chloride,
    stg3.calcium,

    -- 화학 검사
    stg3.temperature,
    stg3.potassium,
    stg3.sodium,
    stg3.lactate,
    stg3.glucose,
    case
        when
            stg3.po2 is null
            or stg3.pco2 is null
            then null
        when stg3.fio2 is not null
            -- fio2는 %라 100으로 나눠 분율로 변환
            then (stg3.fio2 / 100.0) * (760 - 47) - (stg3.pco2 / 0.8) - stg3.po2
        when stg3.fio2_chartevents is not null
            then (stg3.fio2_chartevents / 100.0) * (760 - 47) - (stg3.pco2 / 0.8) - stg3.po2
    end as aado2_calc,
    case
        when stg3.po2 is null
            then null
        when stg3.fio2 is not null
            -- fio2는 %라 100을 곱해 p/f비 산출
            then 100 * stg3.po2 / stg3.fio2
        when stg3.fio2_chartevents is not null
            then 100 * stg3.po2 / stg3.fio2_chartevents
    end as pao2fio2ratio

from stg3
where stg3.lastrowfio2 = 1  -- 가장 최근 fio2 행만
