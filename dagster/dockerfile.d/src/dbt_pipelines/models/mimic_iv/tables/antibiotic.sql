{{ config(tags=['silver']) }}

-- 처방(prescriptions)에서 항생제 처방만 추출한 Silver 모델.
-- drug 명칭을 항생제 상품·성분 패턴 목록과 lower() like로 대조해 antibiotic 플래그를 부여한다.
-- 안약·점이제·국소(크림/젤/연고) 경로 및 base 타입은 제외하고,
-- sepsis-3 계산에 쓰도록 starttime이 속한 icu 재실(stay_id)을 left join으로 붙인다.
-- 출처: mimic-code concepts/medication/antibiotic.sql (BigQuery → Trino 포팅)

with abx as (
    select distinct
        drug,
        route,
        case
            when lower(drug) like '%adoxa%' then 1
            when lower(drug) like '%ala-tet%' then 1
            when lower(drug) like '%alodox%' then 1
            when lower(drug) like '%amikacin%' then 1
            when lower(drug) like '%amikin%' then 1
            when lower(drug) like '%amoxicill%' then 1
            when lower(drug) like '%amphotericin%' then 1
            when lower(drug) like '%anidulafungin%' then 1
            when lower(drug) like '%ancef%' then 1
            when lower(drug) like '%clavulanate%' then 1
            when lower(drug) like '%ampicillin%' then 1
            when lower(drug) like '%augmentin%' then 1
            when lower(drug) like '%avelox%' then 1
            when lower(drug) like '%avidoxy%' then 1
            when lower(drug) like '%azactam%' then 1
            when lower(drug) like '%azithromycin%' then 1
            when lower(drug) like '%aztreonam%' then 1
            when lower(drug) like '%axetil%' then 1
            when lower(drug) like '%bactocill%' then 1
            when lower(drug) like '%bactrim%' then 1
            when lower(drug) like '%bactroban%' then 1
            when lower(drug) like '%bethkis%' then 1
            when lower(drug) like '%biaxin%' then 1
            when lower(drug) like '%bicillin l-a%' then 1
            when lower(drug) like '%cayston%' then 1
            when lower(drug) like '%cefazolin%' then 1
            when lower(drug) like '%cedax%' then 1
            when lower(drug) like '%cefoxitin%' then 1
            when lower(drug) like '%ceftazidime%' then 1
            when lower(drug) like '%cefaclor%' then 1
            when lower(drug) like '%cefadroxil%' then 1
            when lower(drug) like '%cefdinir%' then 1
            when lower(drug) like '%cefditoren%' then 1
            when lower(drug) like '%cefepime%' then 1
            when lower(drug) like '%cefotan%' then 1
            when lower(drug) like '%cefotetan%' then 1
            when lower(drug) like '%cefotaxime%' then 1
            when lower(drug) like '%ceftaroline%' then 1
            when lower(drug) like '%cefpodoxime%' then 1
            when lower(drug) like '%cefpirome%' then 1
            when lower(drug) like '%cefprozil%' then 1
            when lower(drug) like '%ceftibuten%' then 1
            when lower(drug) like '%ceftin%' then 1
            when lower(drug) like '%ceftriaxone%' then 1
            when lower(drug) like '%cefuroxime%' then 1
            when lower(drug) like '%cephalexin%' then 1
            when lower(drug) like '%cephalothin%' then 1
            when lower(drug) like '%cephapririn%' then 1
            when lower(drug) like '%chloramphenicol%' then 1
            when lower(drug) like '%cipro%' then 1
            when lower(drug) like '%ciprofloxacin%' then 1
            when lower(drug) like '%claforan%' then 1
            when lower(drug) like '%clarithromycin%' then 1
            when lower(drug) like '%cleocin%' then 1
            when lower(drug) like '%clindamycin%' then 1
            when lower(drug) like '%cubicin%' then 1
            when lower(drug) like '%dicloxacillin%' then 1
            when lower(drug) like '%dirithromycin%' then 1
            when lower(drug) like '%doryx%' then 1
            when lower(drug) like '%doxycy%' then 1
            when lower(drug) like '%duricef%' then 1
            when lower(drug) like '%dynacin%' then 1
            when lower(drug) like '%ery-tab%' then 1
            when lower(drug) like '%eryped%' then 1
            when lower(drug) like '%eryc%' then 1
            when lower(drug) like '%erythrocin%' then 1
            when lower(drug) like '%erythromycin%' then 1
            when lower(drug) like '%factive%' then 1
            when lower(drug) like '%flagyl%' then 1
            when lower(drug) like '%fortaz%' then 1
            when lower(drug) like '%furadantin%' then 1
            when lower(drug) like '%garamycin%' then 1
            when lower(drug) like '%gentamicin%' then 1
            when lower(drug) like '%kanamycin%' then 1
            when lower(drug) like '%keflex%' then 1
            when lower(drug) like '%kefzol%' then 1
            when lower(drug) like '%ketek%' then 1
            when lower(drug) like '%levaquin%' then 1
            when lower(drug) like '%levofloxacin%' then 1
            when lower(drug) like '%lincocin%' then 1
            when lower(drug) like '%linezolid%' then 1
            when lower(drug) like '%macrobid%' then 1
            when lower(drug) like '%macrodantin%' then 1
            when lower(drug) like '%maxipime%' then 1
            when lower(drug) like '%mefoxin%' then 1
            when lower(drug) like '%metronidazole%' then 1
            when lower(drug) like '%meropenem%' then 1
            when lower(drug) like '%methicillin%' then 1
            when lower(drug) like '%minocin%' then 1
            when lower(drug) like '%minocycline%' then 1
            when lower(drug) like '%monodox%' then 1
            when lower(drug) like '%monurol%' then 1
            when lower(drug) like '%morgidox%' then 1
            when lower(drug) like '%moxatag%' then 1
            when lower(drug) like '%moxifloxacin%' then 1
            when lower(drug) like '%mupirocin%' then 1
            when lower(drug) like '%myrac%' then 1
            when lower(drug) like '%nafcillin%' then 1
            when lower(drug) like '%neomycin%' then 1
            when lower(drug) like '%nicazel doxy 30%' then 1
            when lower(drug) like '%nitrofurantoin%' then 1
            when lower(drug) like '%norfloxacin%' then 1
            when lower(drug) like '%noroxin%' then 1
            when lower(drug) like '%ocudox%' then 1
            when lower(drug) like '%ofloxacin%' then 1
            when lower(drug) like '%omnicef%' then 1
            when lower(drug) like '%oracea%' then 1
            when lower(drug) like '%oraxyl%' then 1
            when lower(drug) like '%oxacillin%' then 1
            when lower(drug) like '%pc pen vk%' then 1
            when lower(drug) like '%pce dispertab%' then 1
            when lower(drug) like '%panixine%' then 1
            when lower(drug) like '%pediazole%' then 1
            when lower(drug) like '%penicillin%' then 1
            when lower(drug) like '%periostat%' then 1
            when lower(drug) like '%pfizerpen%' then 1
            when lower(drug) like '%piperacillin%' then 1
            when lower(drug) like '%tazobactam%' then 1
            when lower(drug) like '%primsol%' then 1
            when lower(drug) like '%proquin%' then 1
            when lower(drug) like '%raniclor%' then 1
            when lower(drug) like '%rifadin%' then 1
            when lower(drug) like '%rifampin%' then 1
            when lower(drug) like '%rocephin%' then 1
            when lower(drug) like '%smz-tmp%' then 1
            when lower(drug) like '%septra%' then 1
            when lower(drug) like '%septra ds%' then 1
            when lower(drug) like '%septra%' then 1
            when lower(drug) like '%solodyn%' then 1
            when lower(drug) like '%spectracef%' then 1
            when lower(drug) like '%streptomycin%' then 1
            when lower(drug) like '%sulfadiazine%' then 1
            when lower(drug) like '%sulfamethoxazole%' then 1
            when lower(drug) like '%trimethoprim%' then 1
            when lower(drug) like '%sulfatrim%' then 1
            when lower(drug) like '%sulfisoxazole%' then 1
            when lower(drug) like '%suprax%' then 1
            when lower(drug) like '%synercid%' then 1
            when lower(drug) like '%tazicef%' then 1
            when lower(drug) like '%tetracycline%' then 1
            when lower(drug) like '%timentin%' then 1
            when lower(drug) like '%tobramycin%' then 1
            when lower(drug) like '%trimethoprim%' then 1
            when lower(drug) like '%unasyn%' then 1
            when lower(drug) like '%vancocin%' then 1
            when lower(drug) like '%vancomycin%' then 1
            when lower(drug) like '%vantin%' then 1
            when lower(drug) like '%vibativ%' then 1
            when lower(drug) like '%vibra-tabs%' then 1
            when lower(drug) like '%vibramycin%' then 1
            when lower(drug) like '%zinacef%' then 1
            when lower(drug) like '%zithromax%' then 1
            when lower(drug) like '%zosyn%' then 1
            when lower(drug) like '%zyvox%' then 1
            else 0
        end as antibiotic
    from {{ source('mimiciv', 'prescriptions') }}
    -- vial/주사기/생리식염수 등 제외
    where
        drug_type not in ('BASE')
        -- 안과(eye)·이과(ear)·국소(topical) 경로 제외
        and route not in ('OU', 'OS', 'OD', 'AU', 'AS', 'AD', 'TP')
        and lower(route) not like '%ear%'
        and lower(route) not like '%eye%'
        -- 국소 크림·젤·연고·탈감작 제형 제외
        and lower(drug) not like '%cream%'
        and lower(drug) not like '%desensitization%'
        and lower(drug) not like '%ophth oint%'
        and lower(drug) not like '%gel%'
-- 확실히 포함: ('IV','PO','PO/NG','ORAL', 'IV DRIP', 'IV BOLUS')
-- 불확실(미분류): VT, PB, PR, PL, NS, NG, NEB, NAS, LOCK, J TUBE, IVT
-- IT, IRR, IP, IO, INHALATION, IN, IM, IJ, IH, G TUBE, DIALYS, enema 등
)

select
    pr.subject_id,
    pr.hadm_id,
    ie.stay_id,
    pr.drug as antibiotic,
    pr.route,
    pr.starttime,
    pr.stoptime
from {{ source('mimiciv', 'prescriptions') }} as pr
-- 항생제 처방으로만 inner join 서브셋
inner join abx
    on pr.drug = abx.drug
    -- 항생제 처방에서 route는 거의 null이 아님(전체 처방 중 ~4000행만 null)
    and pr.route = abx.route
-- sepsis-3 계산에 쓰도록 stay_id 부여
left join {{ source('mimiciv', 'icustays') }} as ie
    on
        pr.hadm_id = ie.hadm_id
        and pr.starttime >= ie.intime
        and pr.starttime < ie.outtime
where abx.antibiotic = 1
