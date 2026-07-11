{{ config(tags=['silver']) }}

-- 기계환기(ventilator) 세팅값을 charttime 단위로 피벗한 Silver 모델.
-- chartevents에서 호흡수·일회호흡량·PlateauPressure·PEEP·FiO2·Flow Rate·환기 모드/유형
-- 관련 itemid를 추출하고, 같은 subject_id·charttime을 한 행으로 모은다.
-- fio2(223835)는 0.2~1 비율값을 %로 환산하고, peep(220339/224700)는 비정상치를 null 처리한다.
-- 출처: mimic-code concepts/measurement/ventilator_setting.sql (BigQuery → Trino 포팅)

with ce as (
    select
        ce.subject_id,
        ce.stay_id,
        ce.charttime,
        ce.itemid,
        ce.value,
        ce.valueuom,
        ce.storetime,
        case
            -- fio2 정제: 0.2~1 비율은 %로 환산, 1~20은 O2 flow(L) 오입력으로 보고 제거
            when ce.itemid = 223835
                then
                    case
                        when ce.valuenum >= 0.20 and ce.valuenum <= 1
                            then ce.valuenum * 100
                        when ce.valuenum > 1 and ce.valuenum < 20
                            then null
                        when ce.valuenum >= 20 and ce.valuenum <= 100
                            then ce.valuenum
                    end
            -- peep 정제: 0~100 범위 밖은 제거
            when ce.itemid in (220339, 224700)
                then
                    case
                        when ce.valuenum > 100 then null
                        when ce.valuenum < 0 then null
                        else ce.valuenum
                    end
            else ce.valuenum
        end as valuenum
    from {{ source('mimiciv', 'chartevents') }} as ce
    where
        ce.value is not null
        and ce.stay_id is not null
        and ce.itemid in (
            224688,  -- respiratory rate (set)
            224689,  -- respiratory rate (spontaneous)
            224690,  -- respiratory rate (total)
            224687,  -- minute volume
            224685, 224684, 224686,  -- tidal volume
            224696,  -- plateau pressure
            220339, 224700,  -- peep
            223835,  -- fio2
            223849,  -- vent mode
            229314,  -- vent mode (hamilton)
            223848,  -- vent type
            224691  -- flow rate (l)
        )
)

select
    subject_id,
    charttime,
    max(stay_id) as stay_id,
    max(case when itemid = 224688 then valuenum end) as respiratory_rate_set,
    max(case when itemid = 224690 then valuenum end) as respiratory_rate_total,
    max(case when itemid = 224689 then valuenum end) as respiratory_rate_spontaneous,
    max(case when itemid = 224687 then valuenum end) as minute_volume,
    max(case when itemid = 224684 then valuenum end) as tidal_volume_set,
    max(case when itemid = 224685 then valuenum end) as tidal_volume_observed,
    max(case when itemid = 224686 then valuenum end) as tidal_volume_spontaneous,
    max(case when itemid = 224696 then valuenum end) as plateau_pressure,
    max(case when itemid in (220339, 224700) then valuenum end) as peep,
    max(case when itemid = 223835 then valuenum end) as fio2,
    max(case when itemid = 224691 then valuenum end) as flow_rate,
    max(case when itemid = 223849 then value end) as ventilator_mode,
    max(case when itemid = 229314 then value end) as ventilator_mode_hamilton,
    max(case when itemid = 223848 then value end) as ventilator_type
from ce
group by subject_id, charttime
