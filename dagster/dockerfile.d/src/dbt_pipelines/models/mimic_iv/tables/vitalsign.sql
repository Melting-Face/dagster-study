{{ config(tags=['silver']) }}

-- ICU 차트이벤트(chartevents)를 charttime 단위로 피벗한 활력징후 와이드 테이블.
-- itemid별 측정값을 컬럼으로 펼치고, 같은 시각의 중복 측정은 평균(avg)으로 집계한다.
-- 침습+비침습 혈압은 통합 컬럼(sbp/dbp/mbp)으로, 비침습은 별도(*_ni)로 분리한다.
-- 공식 mimiciv_derived.vitalsign 포팅 (BigQuery → Trino).
-- 출처: mimic-code mimic-iv/concepts/measurement/vitalsign.sql

select
    ce.subject_id,
    ce.stay_id,
    ce.charttime,
    avg(case
        when ce.itemid in (220045) and ce.valuenum > 0 and ce.valuenum < 300
            then ce.valuenum
    end) as heart_rate,
    avg(case
        when
            ce.itemid in (220179, 220050, 225309)
            and ce.valuenum > 0 and ce.valuenum < 400
            then ce.valuenum
    end) as sbp,
    avg(case
        when
            ce.itemid in (220180, 220051, 225310)
            and ce.valuenum > 0 and ce.valuenum < 300
            then ce.valuenum
    end) as dbp,
    avg(case
        when
            ce.itemid in (220052, 220181, 225312)
            and ce.valuenum > 0 and ce.valuenum < 300
            then ce.valuenum
    end) as mbp,
    avg(case
        when ce.itemid = 220179 and ce.valuenum > 0 and ce.valuenum < 400
            then ce.valuenum
    end) as sbp_ni,
    avg(case
        when ce.itemid = 220180 and ce.valuenum > 0 and ce.valuenum < 300
            then ce.valuenum
    end) as dbp_ni,
    avg(case
        when ce.itemid = 220181 and ce.valuenum > 0 and ce.valuenum < 300
            then ce.valuenum
    end) as mbp_ni,
    avg(case
        when ce.itemid in (220210, 224690) and ce.valuenum > 0 and ce.valuenum < 70
            then ce.valuenum
    end) as resp_rate,
    -- 화씨(223761)는 섭씨로 변환, 섭씨(223762)는 그대로. 소수 2자리 반올림.
    round(avg(case
        when ce.itemid in (223761) and ce.valuenum > 70 and ce.valuenum < 120
            then (ce.valuenum - 32) / 1.8
        when ce.itemid in (223762) and ce.valuenum > 10 and ce.valuenum < 50
            then ce.valuenum
    end), 2) as temperature,
    max(case when ce.itemid = 224642 then ce.value end) as temperature_site,
    avg(case
        when ce.itemid in (220277) and ce.valuenum > 0 and ce.valuenum <= 100
            then ce.valuenum
    end) as spo2,
    avg(case
        when ce.itemid in (225664, 220621, 226537) and ce.valuenum > 0
            then ce.valuenum
    end) as glucose
from {{ source('mimiciv', 'chartevents') }} as ce
where
    ce.stay_id is not null
    and ce.itemid in (
        220045,  -- Heart Rate
        225309,  -- ART BP Systolic
        225310,  -- ART BP Diastolic
        225312,  -- ART BP Mean
        220050,  -- Arterial Blood Pressure systolic
        220051,  -- Arterial Blood Pressure diastolic
        220052,  -- Arterial Blood Pressure mean
        220179,  -- Non Invasive Blood Pressure systolic
        220180,  -- Non Invasive Blood Pressure diastolic
        220181,  -- Non Invasive Blood Pressure mean
        220210,  -- Respiratory Rate
        224690,  -- Respiratory Rate (Total)
        220277,  -- SpO2, peripheral
        225664,  -- Glucose finger stick
        220621,  -- Glucose (serum)
        226537,  -- Glucose (whole blood)
        223762,  -- Temperature Celsius
        223761,  -- Temperature Fahrenheit
        224642  -- Temperature Site
    )
group by ce.subject_id, ce.stay_id, ce.charttime
