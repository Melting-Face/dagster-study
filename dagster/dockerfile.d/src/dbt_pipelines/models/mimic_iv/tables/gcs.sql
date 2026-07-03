{{ config(tags=['silver']) }}

-- Glasgow Coma Scale(GCS)를 charttime 단위로 산출한 Silver 모델.
-- chartevents에서 운동(223901)·언어(223900)·개안(220739) 반응을 추출해 같은
-- subject_id·stay_id·charttime을 한 행으로 모으고, 직전 6시간 내 측정값으로 결측을
-- 보간해 총점(gcs)을 계산한다. 'No Response-ETT'(기관삽관)는 언어 0점·gcs_unable=1.
-- 출처: mimic-code concepts/measurement/gcs.sql (BigQuery → Trino 포팅)

with base as (
    select
        ce.subject_id,
        ce.stay_id,
        ce.charttime,
        max(case when ce.itemid = 223901 then ce.valuenum end) as gcsmotor,
        max(case
            -- 기관삽관(No Response-ETT)은 언어 반응 0점 처리
            when ce.itemid = 223900 and ce.value = 'No Response-ETT' then 0
            when ce.itemid = 223900 then ce.valuenum
        end) as gcsverbal,
        max(case when ce.itemid = 220739 then ce.valuenum end) as gcseyes,
        max(case
            when ce.itemid = 223900 and ce.value = 'No Response-ETT' then 1
            else 0
        end) as endotrachflag,
        row_number() over (
            partition by ce.stay_id
            order by ce.charttime asc
        ) as rn
    from {{ source('mimiciv', 'chartevents') }} as ce
    where ce.itemid in (223900, 223901, 220739)
    group by ce.subject_id, ce.stay_id, ce.charttime
),

gcs as (
    select
        b.subject_id,
        b.stay_id,
        b.charttime,
        b.gcsmotor,
        b.gcsverbal,
        b.gcseyes,
        b.endotrachflag,
        b.rn,
        b2.gcsverbal as gcsverbalprev,
        b2.gcsmotor as gcsmotorprev,
        b2.gcseyes as gcseyesprev,
        case
            when b.gcsverbal = 0
                then 15
            when b.gcsverbal is null and b2.gcsverbal = 0
                then 15
            when b2.gcsverbal = 0
                then
                    coalesce(b.gcsmotor, 6)
                    + coalesce(b.gcsverbal, 5)
                    + coalesce(b.gcseyes, 4)
            else
                coalesce(b.gcsmotor, coalesce(b2.gcsmotor, 6))
                + coalesce(b.gcsverbal, coalesce(b2.gcsverbal, 5))
                + coalesce(b.gcseyes, coalesce(b2.gcseyes, 4))
        end as gcs
    from base as b
    left join base as b2
        on
            b.stay_id = b2.stay_id
            and b.rn = b2.rn + 1
            -- 직전 측정이 6시간 이내일 때만 보간에 사용
            and b2.charttime > b.charttime - interval '6' hour
),

gcs_stg as (
    select
        gs.subject_id,
        gs.stay_id,
        gs.charttime,
        gs.gcs,
        gs.endotrachflag,
        coalesce(gs.gcsmotor, gs.gcsmotorprev) as gcsmotor,
        coalesce(gs.gcsverbal, gs.gcsverbalprev) as gcsverbal,
        coalesce(gs.gcseyes, gs.gcseyesprev) as gcseyes,
        case when coalesce(gs.gcsmotor, gs.gcsmotorprev) is null then 0 else 1 end
        + case when coalesce(gs.gcsverbal, gs.gcsverbalprev) is null then 0 else 1 end
        + case when coalesce(gs.gcseyes, gs.gcseyesprev) is null then 0 else 1 end
            as components_measured
    from gcs as gs
)

select
    gs.subject_id,
    gs.stay_id,
    gs.charttime,
    gs.gcs,
    gs.gcsmotor as gcs_motor,
    gs.gcsverbal as gcs_verbal,
    gs.gcseyes as gcs_eyes,
    gs.endotrachflag as gcs_unable
from gcs_stg as gs
