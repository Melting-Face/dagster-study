{{ config(tags=['silver']) }}

-- 산소 공급 장치·환기 모드를 6개 임상 범주로 분류하고 환기 구간(duration)을 산출하는 Silver 모델.
-- 범주(우선순위 trach > mech vent > NIV > high flow > o2):
--   Tracheostomy / InvasiveVent / NonInvasiveVent / HFNC / SupplementalOxygen / None
-- ventilator_setting·oxygen_delivery(개념 모델)의 charttime을 합집합으로 모아 상태를 판정하고,
-- 14시간 이상 공백이나 상태 변화 시 새 환기 이벤트로 끊어 stay_id·이벤트 단위 구간으로 집계한다.
-- 출처: mimic-code concepts/treatment/ventilation.sql (BigQuery → Trino 포팅)

with tm as (
    -- 관련 기록이 있는 모든 (stay_id, charttime) 합집합
    select
        stay_id,
        charttime
    from {{ ref('ventilator_setting') }}
    union distinct
    select
        stay_id,
        charttime
    from {{ ref('oxygen_delivery') }}
),

vs as (
    select
        tm.stay_id,
        tm.charttime,
        od.o2_delivery_device_1,
        coalesce(vs.ventilator_mode, vs.ventilator_mode_hamilton) as vent_mode,
        -- 우선순위 trach > mech vent > NIV > high flow > o2 순으로 환기 상태 판정
        case
            -- 기관절개(tracheostomy)
            when
                od.o2_delivery_device_1 in (
                    'Tracheostomy tube',
                    'Trach mask '  -- T-piece는 InvasiveVent/Tracheostomy 모호하여 제외
                )
                then 'Tracheostomy'
            -- 침습적 기계환기(invasive ventilation)
            when
                od.o2_delivery_device_1 in (
                    'Endotracheal tube'
                )
                or vs.ventilator_mode in (
                    '(S) CMV',
                    'APRV',
                    'APRV/Biphasic+ApnPress',
                    'APRV/Biphasic+ApnVol',
                    'APV (cmv)',
                    'Ambient',
                    'Apnea Ventilation',
                    'CMV',
                    'CMV/ASSIST',
                    'CMV/ASSIST/AutoFlow',
                    'CMV/AutoFlow',
                    'CPAP/PPS',
                    'CPAP/PSV',
                    'CPAP/PSV+Apn TCPL',
                    'CPAP/PSV+ApnPres',
                    'CPAP/PSV+ApnVol',
                    'MMV',
                    'MMV/AutoFlow',
                    'MMV/PSV',
                    'MMV/PSV/AutoFlow',
                    'P-CMV',
                    'PCV+',
                    'PCV+/PSV',
                    'PCV+Assist',
                    'PRES/AC',
                    'PRVC/AC',
                    'PRVC/SIMV',
                    'PSV/SBT',
                    'SIMV',
                    'SIMV/AutoFlow',
                    'SIMV/PRES',
                    'SIMV/PSV',
                    'SIMV/PSV/AutoFlow',
                    'SIMV/VOL',
                    'SYNCHRON MASTER',
                    'SYNCHRON SLAVE',
                    'VOL/AC'
                )
                or vs.ventilator_mode_hamilton in (
                    'APRV',
                    'APV (cmv)',
                    'Ambient',
                    '(S) CMV',
                    'P-CMV',
                    'SIMV',
                    'APV (simv)',
                    'P-SIMV',
                    'VS',
                    'ASV'
                )
                then 'InvasiveVent'
            -- 비침습 환기(NIV)
            when
                od.o2_delivery_device_1 in (
                    'Bipap mask ',
                    'CPAP mask '
                )
                or vs.ventilator_mode_hamilton in (
                    'DuoPaP',
                    'NIV',
                    'NIV-ST'
                )
                then 'NonInvasiveVent'
            -- 고유량 비강 캐뉼라(HFNC)
            when
                od.o2_delivery_device_1 in (
                    'High flow nasal cannula'
                )
                then 'HFNC'
            -- 보조 산소(non-rebreather 등)
            when
                od.o2_delivery_device_1 in (
                    'Non-rebreather',
                    'Face tent',
                    'Aerosol-cool',
                    'Venti mask ',
                    'Medium conc mask ',
                    'Ultrasonic neb',
                    'Vapomist',
                    'Oxymizer',
                    'High flow neb',
                    'Nasal cannula'
                )
                then 'SupplementalOxygen'
            when
                od.o2_delivery_device_1 in (
                    'None'
                )
                then 'None'
        -- 미분류(other)
        end as ventilation_status
    from tm
    left join {{ ref('ventilator_setting') }} as vs
        on
            tm.stay_id = vs.stay_id
            and tm.charttime = vs.charttime
    left join {{ ref('oxygen_delivery') }} as od
        on
            tm.stay_id = od.stay_id
            and tm.charttime = od.charttime
),

vd0 as (
    select
        stay_id,
        charttime,
        ventilation_status,
        -- 동일 상태에서의 직전 charttime (상태 지속 구간 계산용)
        lag(charttime, 1) over (
            partition by stay_id, ventilation_status
            order by charttime
        ) as charttime_lag,
        -- 상태 무관 다음 charttime (상태 전이 종료 시각용)
        lead(charttime, 1) over (
            partition by stay_id
            order by charttime
        ) as charttime_lead,
        lag(ventilation_status, 1) over (
            partition by stay_id
            order by charttime
        ) as ventilation_status_lag
    from vs
    where ventilation_status is not null
),

vd1 as (
    select
        stay_id,
        charttime,
        charttime_lag,
        charttime_lead,
        ventilation_status,
        -- 직전 이벤트로부터의 경과 시간(시간 단위). 정수 나눗셈 회피 위해 double 캐스트
        cast(date_diff('minute', charttime_lag, charttime) as double) / 60 as ventduration,
        -- 현재 상태가 새 이벤트인지 직전 이벤트의 연속인지 판정
        case
            -- lag가 null이면 환자의 첫 이벤트
            when ventilation_status_lag is null then 1
            -- 14시간 이상 공백은 항상 새 이벤트
            when date_diff('hour', charttime_lag, charttime) >= 14 then 1
            -- 직전 행과 상태가 다르면 새 이벤트
            when ventilation_status_lag != ventilation_status then 1
            else 0
        end as new_ventilation_event
    from vd0
),

vd2 as (
    select
        stay_id,
        charttime,
        charttime_lead,
        ventilation_status,
        ventduration,
        new_ventilation_event,
        -- 새 환기 이벤트 누적합 → 이벤트마다 단조 증가하는 시퀀스 부여
        sum(new_ventilation_event) over (
            partition by stay_id
            order by charttime
        ) as vent_seq
    from vd1
)

select
    stay_id,
    min(charttime) as starttime,
    -- 종료 시각: 다음 세팅의 시각. 단 14시간 이상 공백이면 마지막 기록 시각
    max(
        case
            when
                charttime_lead is null
                or date_diff('hour', charttime, charttime_lead) >= 14
                then charttime
            else charttime_lead
        end
    ) as endtime,
    -- 같은 vent_seq는 동일 ventilation_status → 집계로 대표값 사용
    max(ventilation_status) as ventilation_status
from vd2
group by stay_id, vent_seq
having min(charttime) != max(charttime)
