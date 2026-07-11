{{ config(tags=['silver']) }}

-- 시간당 소변량(urine output rate)을 추정하는 Silver 모델.
-- icustays·chartevents(220045 심박수)에서 stay별 측정 구간을 잡고,
-- urine_output의 각 측정 간 경과시간(분)을 계산한 뒤 6/12/24시간 누적 소변량과
-- 누적 측정시간을 구한다. weight_durations의 체중으로 정규화해
-- mL/kg/hr 단위 신장 기능 지표(uo_mlkghr_6hr/12hr/24hr)를 산출한다.
-- 출처: mimic-code concepts/measurement/urine_output_rate.sql (BigQuery → Trino 포팅)

with tm as (
    select
        ie.stay_id,
        min(ce.charttime) as intime_hr,
        max(ce.charttime) as outtime_hr
    from {{ source('mimiciv', 'icustays') }} as ie
    inner join {{ source('mimiciv', 'chartevents') }} as ce
        on
            ie.stay_id = ce.stay_id
            and ce.itemid = 220045
            and ce.charttime > ie.intime - interval '1' month
            and ce.charttime < ie.outtime + interval '1' month
    group by ie.stay_id
),

uo_tm as (
    select
        tm.stay_id,
        uo.charttime,
        uo.urineoutput,
        case
            when
                lag(uo.charttime) over (
                    partition by tm.stay_id
                    order by uo.charttime
                ) is null
                then date_diff('minute', tm.intime_hr, uo.charttime)
            else
                date_diff(
                    'minute',
                    lag(uo.charttime) over (
                        partition by tm.stay_id
                        order by uo.charttime
                    ),
                    uo.charttime
                )
        end as tm_since_last_uo
    from tm
    inner join {{ ref('urine_output') }} as uo
        on tm.stay_id = uo.stay_id
),

ur_stg as (
    select
        io_cur.stay_id,
        io_cur.charttime,
        -- 동일 charttime 중복 합산 방지를 위해 distinct 합산
        sum(distinct io_cur.urineoutput) as uo,
        -- charttime 기록이 1시간 UO에 대응한다고 가정, 5/11시간으로 구간 제한
        sum(
            case
                when date_diff('hour', iosum.charttime, io_cur.charttime) <= 5
                    then iosum.urineoutput
            end
        ) as urineoutput_6hr,
        sum(
            case
                when date_diff('hour', iosum.charttime, io_cur.charttime) <= 5
                    then iosum.tm_since_last_uo
            end
        ) / 60.0 as uo_tm_6hr,
        sum(
            case
                when date_diff('hour', iosum.charttime, io_cur.charttime) <= 11
                    then iosum.urineoutput
            end
        ) as urineoutput_12hr,
        sum(
            case
                when date_diff('hour', iosum.charttime, io_cur.charttime) <= 11
                    then iosum.tm_since_last_uo
            end
        ) / 60.0 as uo_tm_12hr,
        sum(iosum.urineoutput) as urineoutput_24hr,
        sum(iosum.tm_since_last_uo) / 60.0 as uo_tm_24hr
    from uo_tm as io_cur
    -- 24시간 구간 내 모든 UO 측정과 조인
    left join uo_tm as iosum
        on
            io_cur.stay_id = iosum.stay_id
            and io_cur.charttime >= iosum.charttime
            and io_cur.charttime <= iosum.charttime + interval '23' hour
    group by io_cur.stay_id, io_cur.charttime
)

select
    ur.stay_id,
    ur.charttime,
    wd.weight,
    ur.uo,
    ur.urineoutput_6hr,
    ur.urineoutput_12hr,
    ur.urineoutput_24hr,
    case
        when ur.uo_tm_6hr >= 6
            then round(cast(ur.urineoutput_6hr as double) / wd.weight / ur.uo_tm_6hr, 4)
    end as uo_mlkghr_6hr,
    case
        when ur.uo_tm_12hr >= 12
            then round(cast(ur.urineoutput_12hr as double) / wd.weight / ur.uo_tm_12hr, 4)
    end as uo_mlkghr_12hr,
    case
        when ur.uo_tm_24hr >= 24
            then round(cast(ur.urineoutput_24hr as double) / wd.weight / ur.uo_tm_24hr, 4)
    end as uo_mlkghr_24hr,
    round(ur.uo_tm_6hr, 2) as uo_tm_6hr,
    round(ur.uo_tm_12hr, 2) as uo_tm_12hr,
    round(ur.uo_tm_24hr, 2) as uo_tm_24hr
from ur_stg as ur
left join {{ ref('weight_durations') }} as wd
    on
        ur.stay_id = wd.stay_id
        and ur.charttime > wd.starttime
        and ur.charttime <= wd.endtime
        and wd.weight > 0
