# -*- coding: utf-8 -*-
"""
DDI Rules Master Generator for pharm-ddi-suite
Generates 320+ clinically accurate drug-drug interaction rules.
All drug IDs are strictly verified against builder_drugs.DRUGS.
"""
import json
import builder_drugs
import builder_rules
existing_rules = list(builder_rules.DDI_RULES[:118])
print(f"Loaded existing rules: {len(existing_rules)}")

valid_ids = set(d["id"] for d in builder_drugs.DRUGS)
print(f"Loaded valid drug IDs: {len(valid_ids)}")

# Verify existing rules
for r in existing_rules:
    for did in r["drugs"]:
        if did not in valid_ids:
            raise ValueError(f"Existing rule {r['id']} has invalid drug: {did}")

# Helper to create rule
new_rules = []
rule_counter = 1

def add_rule(drugs, level, title, mechanism, clinical_effect, action_plan, source="K-DUR / 약동학 가이드라인", recent_sci=False, sci_ref=None, dept="원외처방 / 내과 / 가정의학과"):
    global rule_counter
    for did in drugs:
        if did not in valid_ids:
            print(f"Warning: skipped unknown drug ID {did} in rule {title}")
            return
    rid = f"DDI-EXP-{rule_counter:04d}"
    rule_counter += 1

    if level == "금기":
        sev = "CONTRAINDICATED"
        sev_ko = "병용 금기"
    elif level == "중대 위험":
        sev = "MAJOR"
        sev_ko = "중대한 위험"
    else:
        sev = "MODERATE"
        sev_ko = "병용 주의"

    rule = {
        "id": rid,
        "drugs": list(drugs),
        "severity": sev,
        "severity_ko": sev_ko,
        "title": title,
        "mechanism": mechanism,
        "adverse_reactions": [clinical_effect] if isinstance(clinical_effect, str) else clinical_effect,
        "clinical_action": action_plan,
        "hospital_department": dept,
        "is_recent_sci": recent_sci
    }
    if sci_ref:
        rule["sci_journal"] = sci_ref
        rule["sci_year"] = "2024"
        rule["sci_badge"] = "최신 정보 (최근 2개년 SCI)"
    new_rules.append(rule)

# ----------------- Group A: NSAIDs + 항응고제/항혈소판제 출혈 복합 (약 35건 추가) -----------------
nsaids_list = [
    ("ibuprofen", "이부프로펜"), ("naproxen", "나프록센"), ("celecoxib", "세레콕시브"),
    ("loxoprofen", "록소프로펜"), ("meloxicam", "멜록시캄"), ("diclofenac", "디클로페낙"),
    ("aceclofenac", "아세클로페낙"), ("ketoprofen", "케토프로펜"), ("indomethacin", "인도메타신"),
    ("piroxicam", "피록시캄"), ("etodolac", "에토돌락"), ("dexibuprofen", "덱시부프로펜"),
    ("nabumetone", "나부메톤"), ("zaltoprofen", "잘토프로펜"), ("pelubiprofen", "펠루비프로펜")
]

antithrombotic_list = [
    ("warfarin", "와파린", "금기", "비타민K 의존적 응고인자 억제와 위점막 프로스타글란딘 억제 및 혈소판 기능 저해의 복합", "상부 위장관 대출혈, INR 조절 실패, 생명 위협 출혈", "병용 금기 또는 불가피한 경우 아세트아미노펜 대체, PPI(에스오메프라졸) 필수 병용 및 INR 모니터링"),
    ("apixaban", "아픽사반(엘리퀴스)", "중대 위험", "FXa 직접 억제제와 COX-1/2 억제에 의한 혈소판 지혈마개 형성 차단 및 위점막 손상 상가", "위장관 점막 출혈 빈도 3~4배 급증, 빈혈, 흑색변", "단기 사용 시에도 PPI 병용 고려, 위장장애 및 잠혈 징후 철저 감시"),
    ("rivaroxaban", "리바록사반(자렐토)", "중대 위험", "FXa 저해제 항응고 작용과 NSAID의 위점막 방어벽 붕괴 상가작용", "중증 소화관 출혈 위험 급증", "가능한 아세트아미노펜 등으로 진통제 대체, 병용 시 PPI 병용 처방"),
    ("edoxaban", "에독사반(릭시아나)", "중대 위험", "FXa 저해와 혈소판 응집 억제 및 위점막 손상 상승", "소화관 궤양 출혈, 피하 혈종, 혈뇨", "진통제 필요 시 국소 외용제 또는 아세트아미노펜 1차 고려"),
    ("dabigatran", "다비가트란(프라닥사)", "중대 위험", "직접 트롬빈 억제제와 NSAID의 위점막 점식증 유발 상가", "식도염 및 위장관 출혈 위험 상승", "식후 즉시 충분한 물과 복용, PPI 병용 필수"),
    ("clopidogrel", "클로피도그렐(플라빅스)", "중대 위험", "ADP 수용체 차단 혈소판 억제와 COX 억제 혈소판 기능 마비 및 위점막 침식", "위궤양 출혈 발생 위험 2~3배 상승", "세레콕시브 등 위장안전성 제제 우선 또는 PPI 병용"),
    ("ticagrelor", "티카그렐러(브릴린타)", "중대 위험", "가역적 P2Y12 억제제와 NSAID의 지혈 억제 상가", "주요 출혈(자발성 출혈, 위장출혈) 위험 급증", "출혈 고위험군 병용 회피, 필요 시 최소 용량 단기 투여"),
    ("prasugrel", "프라수그렐(에피언트)", "중대 위험", "강력한不可역적 P2Y12 억제와 NSAID의 위점막 손상 상가", "치명적 위장관 및 두개내 출혈 위험", "원칙적 병용 회피, 대체 진통제 선정"),
    ("cilostazol", "실로스타졸(프레탈)", "주의", "PDE3 억제 혈소판 응집 저해와 NSAID 혈소판 기능 저해 상가", "점막 출혈, 멍, 반상출혈 빈도 증가", "출혈 징후 모니터링, 필요 시 투여 간격 조정")
]

# Add systematic NSAID + Antithrombotic rules (selected high-impact pairs)
for at_id, at_name, at_lvl, at_mech, at_eff, at_act in antithrombotic_list:
    for ns_id, ns_name in nsaids_list:
        # Check if pair already exists in existing_rules
        pair_set = {at_id, ns_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules):
            add_rule(
                [at_id, ns_id],
                at_lvl,
                f"{at_name} + {ns_name} 병용 시 출혈 및 위장관 궤양 위험",
                f"{at_name}의 {at_mech}",
                f"{ns_name} 복용으로 {at_eff}",
                at_act,
                source="식약처 DUR 및 K-DUR 병용주의"
            )

print(f"Rules after Group A: {len(existing_rules) + len(new_rules)}")

# ----------------- Group B: 세로토닌 증후군 (Serotonin Syndrome) -----------------
serotonergic_agents = [
    ("fluoxetine", "플루옥세틴"), ("sertraline", "설트랄린"), ("paroxetine", "파록세틴"),
    ("escitalopram", "에스시탈로프람"), ("citalopram", "시탈로프람"), ("fluvoxamine", "플루복사민"),
    ("venlafaxine", "벤라팍신"), ("duloxetine", "둘록세틴"), ("desvenlafaxine", "데스벤라팍신"),
    ("vortioxetine", "보티옥세틴"), ("mirtazapine", "미르타자핀"), ("trazodone", "트라조돈")
]

serotonin_triggers = [
    ("tramadol", "트라마돌", "금기", "세로토닌 재흡수 억제 및 세로토닌 방출 촉진 상가", "치명적 세로토닌 증후군(고열, 간대성경련, 혼수), 경련 발작 역치 강하", "병용 회피, 비마약성 진통제 또는 순수 오피오이드 검토"),
    ("fentanyl", "펜타닐", "금기", "중추 5-HT 수용체 자극 및 세로토닌 농도 급증 상가", "세로토닌 증후군, 호흡 억제 복합", "중환자/수술실 세로토닌 독성 모니터링, 병용 시 긴급 길항제 대비"),
    ("pethidine", "페티딘", "금기", "강력한 세로토닌 재흡수 차단 작용과 항우울제의 시너지", "악성 고열, 혼수, 심혈관 불안정성 세로토닌 쇼크 (DUR 절대금기)", "절대 병용 금기, 모르핀 등 대체 진통제 투여"),
    ("dextromethorphan", "덱스트로메토르판", "금기", "중추 세로토닌 재흡수 억제(SRI) 복합 작용", "세로토닌 증후군(혼란, 발한, 반사항진, 진전)", "일반의약품/전문진해제 성분 확인 필수, 레보드로프로피진 대체"),
    ("linezolid", "리네졸리드", "금기", "비선택적 가역적 MAO 억제 작용으로 세로토닌 대사 전면 차단", "신속하고 치명적인 세로토닌 증후군 발생", "DUR 절대금기, 리네졸리드 투여 2주 전 항우울제 중단 필수"),
    ("sumatriptan", "수마트립탄", "중대 위험", "5-HT 1B/1D 효능제와 시냅스 세로토닌 증가 상가", "세로토닌 증후군, 뇌혈관 연축 위험", "동시 투여 주의, 이상 감각/근강직 발생 시 즉시 중단"),
    ("zolmitriptan", "졸미트립탄", "중대 위험", "5-HT 수용체 활성화 상가", "세로토닌 독성 징후 및 혈압 급상승", "동시 복용 회피, 복용 간격 24시간 분리")
]

for s_id, s_name in serotonergic_agents:
    for t_id, t_name, t_lvl, t_mech, t_eff, t_act in serotonin_triggers:
        pair_set = {s_id, t_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            add_rule(
                [s_id, t_id],
                t_lvl,
                f"{s_name} + {t_name} 세로토닌 증후군 위험",
                f"{s_name}과 {t_name}의 {t_mech}",
                f"시냅스 내 세로토닌 과잉 축적으로 {t_eff}",
                t_act,
                source="식약처 DUR 병용금기 / FDA Black Box 경고"
            )

print(f"Rules after Group B: {len(existing_rules) + len(new_rules)}")

# ----------------- Group C: QT 연장 및 Torsades de Pointes (심실부정맥) -----------------
qt_cardiac = [("amiodarone", "아미오다론"), ("sotalol", "소탈롤"), ("flecainide", "플레카이니드")]
qt_antiinfective = [
    ("clarithromycin", "클라리스로마이신"), ("azithromycin", "아지스로마이신"),
    ("ciprofloxacin", "시프로플록사신"), ("levofloxacin", "레보플록사신"),
    ("moxifloxacin", "목시플록사신"), ("fluconazole", "플루코나졸"), ("voriconazole", "보리코나졸")
]
qt_psych = [
    ("haloperidol", "할로페리돌"), ("quetiapine", "퀘티아핀"), ("olanzapine", "올란자핀"),
    ("risperidone", "리스페리돈"), ("aripiprazole", "아리피프라졸"), ("chlorpromazine", "클로르프로마진"),
    ("escitalopram", "에스시탈로프람"), ("citalopram", "시탈로프람"), ("amisulpride", "아미설프리드")
]
qt_gastro = [("ondansetron", "온단세트론"), ("domperidone", "돔페리돈")]

all_qt_drugs = qt_cardiac + qt_antiinfective + qt_psych + qt_gastro

# Generate pairwise high-risk QT interactions
for i in range(len(all_qt_drugs)):
    for j in range(i + 1, len(all_qt_drugs)):
        d1_id, d1_name = all_qt_drugs[i]
        d2_id, d2_name = all_qt_drugs[j]
        # Only cross groups or cardiac combinations
        pair_set = {d1_id, d2_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            # Prioritize significant combos
            level = "금기" if (d1_id in ["amiodarone", "sotalol", "moxifloxacin"] or d2_id in ["amiodarone", "sotalol", "moxifloxacin"]) else "중대 위험"
            add_rule(
                [d1_id, d2_id],
                level,
                f"{d1_name} + {d2_name} 심장 IKr 채널 차단 및 QT 연장 / TdP 위험",
                f"{d1_name}과 {d2_name}의 심근 지연정류 칼륨전류(IKr) 동시 차단 및 심실 재분극 지연 상가작용",
                "심전도 QTc 간격 위험 수준(>500ms) 연장, Torsades de Pointes (TdP) 및 치명적 심실세동/심정지",
                "병용 투여 회피, 전해질(K+, Mg2+) 교정 필수, 불가피한 병용 시 투여 전후 심전도 모니터링",
                source="식약처 DUR 병용금기 / CredibleMeds QT 가이드라인"
            )

print(f"Rules after Group C: {len(existing_rules) + len(new_rules)}")

# ----------------- Group D: CYP3A4 강력 저해제 x 고위험 기질 -----------------
cyp3a4_inhibitors = [
    ("itraconazole", "이트라코나졸", "강력"), ("voriconazole", "보리코나졸", "강력"),
    ("clarithromycin", "클라리스로마이신", "강력"), ("ketoconazole", "케토코나졸", "강력"),
    ("diltiazem", "딜티아젬", "중등도"), ("verapamil", "베라파밀", "중등도")
]

cyp3a4_substrates = [
    ("simvastatin", "심바스타틴", "금기", "간내 대사 차단으로 스타틴 혈중농도 최대 10~20배 폭증", "극심한 횡문근융해증(Rhabdomyolysis), 미오글로빈뇨 신부전, 급성 사망", "병용 금기! 아토르바스타틴 최저용량 또는 로수바스타틴/피타바스타틴 대체"),
    ("atorvastatin", "아토르바스타틴", "중대 위험", "간내 CYP3A4 대사 억제로 혈중 AUC 2~4배 상승", "근육통, CPK 상승, 횡문근융해증 발병 위험 증가", "아토르바스타틴 20mg 이하 감량 또는 비CYP 대사 스타틴(프라바스타틴) 전환"),
    ("colchicine", "콜키신", "금기", "CYP3A4 및 P-gp 이중 억제로 콜키신 체내 청소율 소실", "다발성 장기부전, 급성 골수억제, 신경근병증 및 치명적 사망 (식약처 절대금기)", "절대 병용 금기! 통풍 발작 시 NSAIDs 또는 단기 스테로이드 대체"),
    ("triazolam", "트리아졸람", "금기", "초회통과효과 및 간대사 억제로 트리아졸람 반감기 3~5배 연장", "중증 혼수, 역설적 호흡억제, 지속적 무의식 상태 (식약처 병용금기)", "병용 절대 금기! 로라제팜 등 글루쿠론산화 대사 약물로 변경"),
    ("midazolam", "미다졸람", "금기", "CYP3A4 대사 전면 차단으로 진정 작용 극대화", "심각한 호흡 부전, 각성 지연, 저혈압 쇼크", "병용 금기, 진정 내시경 전 투약 이력 반드시 확인"),
    ("alprazolam", "알프라졸람", "중대 위험", "간 대사 저하로 알프라졸람 체내 축적", "주간 과다 진정, 운동실조, 낙상/골절, 호흡 억제", "알프라졸람 용량 50% 이상 감량 및 임상 증상 밀착 관찰"),
    ("cyclosporine", "사이클로스포린", "중대 위험", "면역억제제 청소율 급감으로 혈중 트로프 농도 독성 범위 초과", "급성 신독성(세뇨관 괴사), 신경독성, 중증 고혈압", "면역억제제 TDM(혈중농도 모니터링) 필수, 투여량 선제적 50% 감량"),
    ("tacrolimus", "타크로리무스", "중대 위험", "CYP3A4/P-gp 억제로 타크로리무스 농도 급상승", "중증 신부전, 진전, 전해질 이상(고칼륨혈증)", "혈중 타크로리무스 농도 주 2~3회 측정 및 용량 조절"),
    ("fentanyl", "펜타닐", "금기", "펜타닐 산화적 대사 차단으로 전신 노출량 급증", "치명적 호흡 억제, 혼수, 심정지", "병용 금기 또는 중환자실 집중 모니터링 하에 펜타닐 감량"),
    ("rivaroxaban", "리바록사반", "금기", "CYP3A4와 P-gp 동시 억제로 항응고제 청소율 차단", "전신 주요 장기 대출혈, 두개내 출혈 치명 위험", "병용 금기! 아픽사반/리바록사반 피하고 와파린/헤파린 검토"),
    ("apixaban", "아픽사반", "중대 위험", "CYP3A4/P-gp 이중 억제로 생체이용률 2배 상승", "출혈 합병증 위험 대폭 증가", "강력 억제제 병용 시 아픽사반 용량 50% 감량(2.5mg bid) 필수"),
    ("sildenafil", "실데나필", "금기", "PDE5 억제제 대사 지연으로 혈관확장 효과 폭증", "급격한 저혈압 쇼크, 실신, 심근경색, 시신경 허혈", "강력 CYP3A4 저해제 투여 시 실데나필 병용 회피 또는 25mg 이하 제한"),
    ("tadalafil", "타다라필", "중대 위험", "긴 반감기의 타다라필 대사 차단으로 체내 고농도 지속", "지속발기증(Priapism), 악성 기립성 저혈압, 어지럼", "타다라필 5mg 이하 감량 투여 및 혈압 감시"),
    ("amlodipine", "암로디핀", "주의", "CYP3A4 중등도/강력 억제로 암로디핀 청소율 30~50% 감소", "말초 부종, 안면홍조, 두통, 과도한 저혈압", "암로디핀 2.5~5mg 감량 검토 및 혈압 일일 체크")
]

for inh_id, inh_name, inh_pot in cyp3a4_inhibitors:
    for sub_id, sub_name, sub_lvl, sub_mech, sub_eff, sub_act in cyp3a4_substrates:
        pair_set = {inh_id, sub_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            lvl = sub_lvl if inh_pot == "강력" else ("중대 위험" if sub_lvl == "금기" else "주의")
            add_rule(
                [inh_id, sub_id],
                lvl,
                f"{inh_name} + {sub_name} CYP3A4 대사 저해 및 독성 급증",
                f"{inh_name}의 CYP3A4 대사효소 차단으로 인한 {sub_mech}",
                sub_eff,
                sub_act,
                source="식약처 DUR 병용금기 / 약동학 상호작용"
            )

print(f"Rules after Group D: {len(existing_rules) + len(new_rules)}")

# ----------------- Group E: Triple Whammy (신부전 유발 3종 복합 및 고칼륨혈증) -----------------
ras_blockers = [
    ("losartan", "로사르탄"), ("telmisartan", "텔미사르탄"), ("valsartan", "발사르탄"),
    ("candesartan", "칸데사르탄"), ("olmesartan", "올메사르탄"), ("fimasartan", "피마사르탄"),
    ("ramipril", "라미프릴"), ("perindopril", "페린도프릴"), ("enalapril", "에날라프릴")
]

diuretics = [
    ("furosemide", "푸로세미드"), ("torsemide", "토르세미드"),
    ("hydrochlorothiazide", "히드로클로로티아지드"), ("spironolactone", "스피로노락톤"),
    ("eplerenone", "에플레레논")
]

core_nsaids = [
    ("ibuprofen", "이부프로펜"), ("naproxen", "나프록센"), ("celecoxib", "세레콕시브"),
    ("loxoprofen", "록소프로펜"), ("meloxicam", "멜록시캄"), ("aceclofenac", "아세클로페낙")
]

# RAS + NSAID combinations
for r_id, r_name in ras_blockers:
    for n_id, n_name in core_nsaids:
        pair_set = {r_id, n_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            add_rule(
                [r_id, n_id],
                "중대 위험",
                f"{r_name} + {n_name} 신사구체 혈류 저하 및 급성 신손상(AKI)",
                f"{r_name}의 수출소동맥 확장과 {n_name}의 신혈관 프로스타글란딘 억제(수입소동맥 수축) 기전 길항",
                "신사구체 여과압 급감으로 급성 신부전(AKI), 혈압 조절 실패, 고칼륨혈증",
                "신기능 취약자(고령, 만성신부전) 병용 회피, 필요 시 아세트아미노펜 대체, Cr/eGFR 모니터링",
                source="K-DUR 약물안전성 경보"
            )

# RAS + Spironolactone / Potassium combinations (고칼륨혈증 치명)
for r_id, r_name in ras_blockers:
    # with spironolactone
    pair_set = {r_id, "spironolactone"}
    if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
        add_rule(
            [r_id, "spironolactone"],
            "중대 위험",
            f"{r_name} + 스피로노락톤 알도스테론 이중 억제 고칼륨혈증",
            f"{r_name}의 안지오텐신 억제와 스피로노락톤의 원위세뇨관 알도스테론 수용체 차단에 의한 칼륨 배설 전면 차단",
            "치명적 고칼륨혈증(>6.0 mEq/L), 심근 전도장애, 심실세동 및 심정지",
            "혈청 칼륨 및 크레아티닌 투여 1주, 1개월 후 정기 추적, 고칼륨 식이 제한",
            source="대한신장학회 / 식약처 안전성 서한"
        )
    # with potassium_chloride
    pair_set = {r_id, "potassium_chloride"}
    if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
        add_rule(
            [r_id, "potassium_chloride"],
            "금기",
            f"{r_name} + 염화칼륨 치명적 고칼륨혈증 유발 (병용금기)",
            f"{r_name}의 신장 칼륨 배설 억제 상태에서 외인성 칼륨 직접 보충에 의한 칼륨 급축적",
            "심정지 유발성 고칼륨혈증 쇼크, 전도차단",
            "저칼륨혈증이 명확히 확인된 경우 외 병용 금기, 정기적 전해질 모니터링",
            source="식약처 DUR 병용금기"
        )

print(f"Rules after Group E: {len(existing_rules) + len(new_rules)}")

# ----------------- Group F: 메토트렉세이트 (MTX) 배설 저해 및 골수억제 -----------------
mtx_perps = [
    ("ibuprofen", "이부프로펜", "금기", "신세뇨관 배설 경쟁 억제로 MTX 청소율 급감"),
    ("naproxen", "나프록센", "금기", "단백 결합 치환 및 신장 프로스타글란딘 억제 배설 차단"),
    ("celecoxib", "세레콕시브", "중대 위험", "신세뇨관 배설 지연 및 혈중 MTX 농도 상승"),
    ("loxoprofen", "록소프로펜", "금기", "신배설 억제로 혈중 류마티스 MTX 농도 독성 레벨 도달"),
    ("meloxicam", "멜록시캄", "금기", "MTX 신클리어런스 저해 및 골수독성 증폭"),
    ("diclofenac", "디클로페낙", "금기", "MTX 혈중 농도 급상승 및 급성 간/신부전"),
    ("aspirin", "아스피린", "금기", "혈장 단백질 결합 경쟁적 유리 및 세뇨관 분비 억제"),
    ("omeprazole", "오메프라졸", "중대 위험", "BCRP 수송체 억제 및 위산 의존적 배설 지연"),
    ("esomeprazole", "에스오메프라졸", "중대 위험", "MTX 대사체 및 원형 신배설 억제"),
    ("pantoprazole", "판토프라졸", "중대 위험", "MTX 혈중 농도 지속 상승 유지"),
    ("trimethoprim_sulfamethoxazole", "코트리목사졸(셉트린)", "금기", "상가적 엽산 대사 전면 차단 (항엽산 시너지)")
]

for p_id, p_name, p_lvl, p_mech in mtx_perps:
    pair_set = {"methotrexate", p_id}
    if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
        add_rule(
            ["methotrexate", p_id],
            p_lvl,
            f"메토트렉세이트(MTX) + {p_name} 골수억제 및 치명적 독성",
            f"{p_name}의 {p_mech}",
            "중증 백혈구감소증, 범혈구감소증(Pancytopenia), 소화관 점막염, 패혈증 쇼크",
            "DUR 병용 금기 확인, 고용량 MTX 투여 시 절대 병용 금지, 저용량 류마티스 복용 시에도 혈구수치(CBC) 매주 감시",
            source="식약처 DUR 병용금기 / 대한류마티스학회"
        )

print(f"Rules after Group F: {len(existing_rules) + len(new_rules)}")

# ----------------- Group G: 리튬(Lithium) 독성 (배설 억제) -----------------
lithium_perps = [
    ("ibuprofen", "이부프로펜", "중대 위험", "신장 수입소동맥 수축으로 리튬 배설 30~50% 감소"),
    ("naproxen", "나프록센", "중대 위험", "신혈류량 감소로 리튬 배설 억제"),
    ("celecoxib", "세레콕시브", "중대 위험", "COX-2 억제로 리튬 세뇨관 재흡수 촉진"),
    ("diclofenac", "디클로페낙", "중대 위험", "리튬 신클리어런스 저하"),
    ("losartan", "로사르탄", "중대 위험", "나트륨 배설 촉진에 따른 보상성 리튬 세뇨관 재흡수 급증"),
    ("telmisartan", "텔미사르탄", "중대 위험", "나트륨 소실 유도로 리튬 축적"),
    ("enalapril", "에날라프릴", "중대 위험", "ACE 억제로 알도스테론 저하 및 리튬 배설 저하"),
    ("ramipril", "라미프릴", "중대 위험", "리튬 청소율 감소로 혈중 농도 급증"),
    ("hydrochlorothiazide", "히드로클로로티아지드", "금기", "원위세뇨관 나트륨 배설로 근위세뇨관 리튬 재흡수 폭증"),
    ("furosemide", "푸로세미드", "중대 위험", "체액 탈수 및 전해질 불균형으로 리튬 독성 유발")
]

for p_id, p_name, p_lvl, p_mech in lithium_perps:
    pair_set = {"lithium", p_id}
    if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
        add_rule(
            ["lithium", p_id],
            p_lvl,
            f"리튬 + {p_name} 리튬 배설 장애 및 중추신경 독성",
            f"{p_name} 투여로 인한 {p_mech}",
            "혈중 리튬 농도 위험 수준(>1.5 mEq/L) 상승, 조대진전, 혼돈, 발작, 비가역적 뇌손상",
            "병용 회피 또는 리튬 농도 집중 모니터링, 리튬 용량 30~50% 감량",
            source="대한신경정신의학회 / K-DUR"
        )

print(f"Rules after Group G: {len(existing_rules) + len(new_rules)}")

# ----------------- Group H: 2가/3가 양이온 킬레이트 형성 흡수 억제 -----------------
chelate_antibiotics = [
    ("ciprofloxacin", "시프로플록사신"), ("levofloxacin", "레보플록사신"),
    ("moxifloxacin", "목시플록사신"), ("doxycycline", "독시사이클린"),
    ("minocycline", "미노사이클린")
]

minerals = [
    ("antacid_ca_mg", "제산제 (칼슘/마그네슘)", "중대 위험", "2가/3가 금속 양이온과 난용성 킬레이트 착체 형성으로 위장관 흡수 전면 차단", "항생제 생체이용률 70~90% 격감, 중증 감염 치료 실패 및 균 교대현상", "복용 시간 최소 2~4시간 분리 투여 (항생제 복용 2시간 전 또는 4시간 후 제산제 복용)"),
    ("calcium_carbonate", "탄산칼슘", "중대 위험", "칼슘 이온(Ca2+)과의 불용성 착물 형성", "항생물질 흡수 저하로 혈중 유효 살균 농도 미달", "2시간 이상 시간 간격 엄수"),
    ("magnesium_hydroxide", "수산화마그네슘", "중대 위험", "마그네슘(Mg2+)과의 킬레이트 형성", "항균 효과 심각한 저하", "투여 간격 3시간 이상 분리"),
    ("ferrous_sulfate", "황산제일철", "중대 위험", "철분(Fe2+)과의 강력한 킬레이트 결합", "항생제 및 철분 양측 흡수율 80% 이상 소실", "최소 2시간 이상 간격 두고 투여")
]

for a_id, a_name in chelate_antibiotics:
    for m_id, m_name, m_lvl, m_mech, m_eff, m_act in minerals:
        pair_set = {a_id, m_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            add_rule(
                [a_id, m_id],
                m_lvl,
                f"{a_name} + {m_name} 킬레이트 결합에 의한 흡수 저하",
                f"{m_name}의 {m_mech}",
                m_eff,
                m_act,
                source="약동학 약물상호작용 / K-DUR 복약지도"
            )

print(f"Rules after Group H: {len(existing_rules) + len(new_rules)}")

# ----------------- Group I: CYP2C19 저해제 x 클로피도그렐 (항혈소판 약효 차단) -----------------
cyp2c19_ppis = [
    ("omeprazole", "오메프라졸", "금기", "CYP2C19 강력 경쟁적 억제로 전구약물(Prodrug) 클로피도그렐의 활성 대사체 생성 50% 차단", "스텐트 혈전증, 급성 심근경색 재발, 심혈관계 사망 위험 급증", "오메프라졸/에스오메프라졸 병용 금기! CYP2C19 영향 없는 판토프라졸 또는 라베프라졸로 변경"),
    ("esomeprazole", "에스오메프라졸", "금기", "CYP2C19 억제를 통한 클로피도그렐 활성화 저해", "항혈소판 효과 저하 및 혈전 사건 위험 상승", "판토프라졸 등 안전한 대체 PPI 사용 권고"),
    ("dexlansoprazole", "덱스란소프라졸", "주의", "CYP2C19 부분 억제", "항혈소판 효과 경미한 간섭 가능성", "임상 경과 관찰 또는 대체 고려")
]

for p_id, p_name, p_lvl, p_mech, p_eff, p_act in cyp2c19_ppis:
    pair_set = {"clopidogrel", p_id}
    if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
        add_rule(
            ["clopidogrel", p_id],
            p_lvl,
            f"클로피도그렐 + {p_name} 활성화 억제 및 심근경색 재발 위험",
            p_mech,
            p_eff,
            p_act,
            source="식약처 DUR 병용금기 / FDA Drug Safety Communication"
        )

# ----------------- Group J: 베타차단제 x Non-DHP CCB (치명적 서맥 / 방실차단) -----------------
bb_list = [
    ("bisoprolol", "비소프롤롤"), ("carvedilol", "카베딜롤"),
    ("nebivolol", "네비볼롤"), ("metoprolol", "메토프로롤"),
    ("atenolol", "아테놀롤"), ("propranolol", "프로프라놀롤")
]
non_dhp_list = [("verapamil", "베라파밀"), ("diltiazem", "딜티아젬")]

for b_id, b_name in bb_list:
    for c_id, c_name in non_dhp_list:
        pair_set = {b_id, c_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            lvl = "금기" if c_id == "verapamil" else "중대 위험"
            add_rule(
                [b_id, c_id],
                lvl,
                f"{b_name} + {c_name} 방실전도 차단 및 중증 서맥/심부전 악화",
                f"{b_name}의 베타-1 차단과 {c_name}의 SA/AV 결절 칼슘 유입 차단이 상가적으로 작용하여 심장 전도계 전면 억제",
                "동정지(Sinus arrest), 완전 방실차단(3도 AV block), 심인성 쇼크, 급성 심부전 악화",
                "원칙적 병용 금기(특히 베라파밀 경구/주사). 불가피할 경우 혈압/맥박 집중 모니터링",
                source="식약처 DUR 병용금기 / 대한심장학회"
            )

print(f"Rules after Group J: {len(existing_rules) + len(new_rules)}")

# ----------------- Group K: PDE5 억제제 x 질산염 제제 (절대금기 저혈압 쇼크) -----------------
pde5_list = [
    ("sildenafil", "실데나필"), ("tadalafil", "타다라필"),
    ("vardenafil", "바데나필"), ("udenafil", "유데나필"), ("mirodenafil", "미로데나필")
]
nitrate_list = [
    ("nitroglycerin", "니트로글리세린"),
    ("isosorbide_mononitrate", "이소소르비드 일질산염"),
    ("isosorbide_dinitrate", "이소소르비드 이질산염"),
    ("nicorandil", "니코란딜")
]

for p_id, p_name in pde5_list:
    for n_id, n_name in nitrate_list:
        pair_set = {p_id, n_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            add_rule(
                [p_id, n_id],
                "금기",
                f"{p_name} + {n_name} 치명적 저혈압 쇼크 유발 (절대 병용금기)",
                f"{n_name}의 NO 방출로 증가한 cGMP를 {p_name}가 분해 억제하여 세포내 cGMP 폭발적 축적 및 전신 동정맥 극단적 확장",
                "극심하고 비가역적인 저혈압 쇼크, 관상동맥 관류압 상실, 심근경색, 급성 심장사",
                "DUR 절대 병용 금기! 질산염 복용 환자는 PDE5 억제제 최소 24~48시간 복용 금지",
                source="식약처 DUR 병용금기 / AHA/ACC 가이드라인"
            )

print(f"Rules after Group K: {len(existing_rules) + len(new_rules)}")

# ----------------- Group L: 벤조디아제핀/수면진정제 x 오피오이드 (호흡억제/사망) -----------------
benzo_sedatives = [
    ("alprazolam", "알프라졸람"), ("lorazepam", "로라제팜"),
    ("diazepam", "디아제팜"), ("clonazepam", "클로나제팜"),
    ("zolpidem", "졸피뎀"), ("triazolam", "트리아졸람")
]
opioids = [
    ("tramadol", "트라마돌"), ("oxycodone", "옥시코돈"),
    ("fentanyl", "펜타닐"), ("codeine", "코데인"),
    ("morphine", "모르핀")
]

for b_id, b_name in benzo_sedatives:
    for o_id, o_name in opioids:
        pair_set = {b_id, o_id}
        if not any(set(r["drugs"]) == pair_set for r in existing_rules) and not any(set(r["drugs"]) == pair_set for r in new_rules):
            add_rule(
                [b_id, o_id],
                "중대 위험",
                f"{b_name} + {o_name} 중추신경계 및 호흡 중추 억제 상가작용",
                f"GABA 수용체 활성화와 mu-오피오이드 수용체 자극이 연수 호흡중추 화학수용체 감도를 극도로 억제",
                "깊은 진정, 혼수, 치명적 호흡 억제(Bradypnea), 무호흡증 및 호흡정지 사망",
                "FDA Black Box Warning / DUR 주의 경보. 병용 시 최저 유효 용량 및 최단 기간 투여, 보호자 호흡 감시 지도",
                source="FDA Boxed Warning / 식약처 안전성 서한"
            )

print(f"Rules after Group L: {len(existing_rules) + len(new_rules)}")

# Combine all rules
ALL_RULES = existing_rules + new_rules
print(f"Total Rules Generated: {len(ALL_RULES)}")

# Write to builder_rules.py
with open("builder_rules.py", "w", encoding="utf-8") as f:
    f.write("# -*- coding: utf-8 -*-\n")
    f.write('"""\n')
    f.write(f"DDI Rules Master Data Module ({len(ALL_RULES)} rules)\n")
    f.write('"""\n\n')
    f.write("DDI_RULES = [\n")
    for r in ALL_RULES:
        f.write(f"    {repr(r)},\n")
    f.write("]\n")

print("builder_rules.py successfully generated!")
