# -*- coding: utf-8 -*-
"""
DDI 지식베이스 일일 자동 업데이트 엔진 (auto_update.py)

1) 미조회 검색어 큐: 사이트에서 검색했지만 DB에 없던 약물명을 data/pending_queries.json 에 저장
2) 일일 배치 (기본 매일 03:00, Asia/Seoul):
   - 대기 검색어를 NLM RxNorm 으로 성분명 정규화 → 신규 의약품 등록
   - NLM RxClass(ATC) 동일 계열 유사 약물 자동 등록
   - openFDA 허가사항(라벨) 'Drug Interactions / Contraindications' 원문에서
     DB 내 약물과의 상호작용 후보를 추출하여 DDI 규칙으로 등록
   - 직전 실행 이후 개정된 FDA 라벨(최신순)을 조회하여 기존 약물의 상호작용 규칙 갱신

자동 수집 데이터는 모두 auto_imported=True / needs_review=True 로 표시되며,
절대 '병용 금기(CONTRAINDICATED)' 등급으로 자동 분류하지 않습니다(약사 검증 필요).
기존에 수작업으로 큐레이션된 의약품/규칙은 덮어쓰지 않습니다(삽입 전용).

외부 의존성 없음 (파이썬 표준 라이브러리만 사용).
CLI:  python auto_update.py [--max-queries N] [--no-labels] [--git]
"""

import os
import re
import html
import json
import time
import difflib
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import data_store
from data_store import load_json, save_json, DATA_DIR, DRUGS_FILE, RULES_FILE

PENDING_FILE = os.path.join(DATA_DIR, "pending_queries.json")
STATE_FILE = os.path.join(DATA_DIR, "auto_update_state.json")
UPDATE_LOG_FILE = os.path.join(DATA_DIR, "update_log.json")

RXNAV = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"

UPDATE_HOUR = int(os.environ.get("DATA_UPDATE_HOUR", "3"))
MAX_QUERIES_PER_RUN = int(os.environ.get("DATA_UPDATE_MAX_QUERIES", "20"))
MAX_SIMILAR_PER_DRUG = int(os.environ.get("DATA_UPDATE_MAX_SIMILAR", "5"))
MAX_REQUESTS_PER_RUN = int(os.environ.get("DATA_UPDATE_MAX_REQUESTS", "600"))
MAX_RECENT_LABELS = int(os.environ.get("DATA_UPDATE_MAX_RECENT_LABELS", "1000"))
LABEL_OVERLAP_DAYS = int(os.environ.get("DATA_UPDATE_LABEL_OVERLAP_DAYS", "60"))
FIRST_RUN_LABEL_DAYS = int(os.environ.get("DATA_UPDATE_FIRST_RUN_DAYS", "365"))
MAX_ATTEMPTS = 5
OPENFDA_API_KEY = os.environ.get("OPENFDA_API_KEY", "").strip()
USER_AGENT = "Pharm-DDI-AutoUpdater/1.0 (+https://github.com/ralf-kang/Pharm-DDI)"

_queue_lock = threading.Lock()
_run_lock = threading.Lock()
_run_status = {"running": False, "started_at": None, "trigger": None}

# ATC 코드 접두어 → 기존 DRUG_CATEGORIES (긴 접두어 우선)
ATC_CATEGORY_MAP = [
    ("M01", "소염진통제 (NSAIDs / 진통제)"),
    ("N02", "소염진통제 (NSAIDs / 진통제)"),
    ("B01", "항혈전제 (항혈소판제 / 항응고제)"),
    ("C10", "항지질혈증 (스타틴계 / 피브레이트)"),
    ("C", "심혈관계 / 항고혈압제"),
    ("J01", "항균제 / 항생제"),
    ("J04", "항균제 / 항생제"),
    ("J02", "항진균제 / 항바이러스제"),
    ("J05", "항진균제 / 항바이러스제"),
    ("D01", "항진균제 / 항바이러스제"),
    ("N03", "정신신경용제 (항우울제 / 진정제 / 신경안정제 / 항전간제)"),
    ("N04", "정신신경용제 (항우울제 / 진정제 / 신경안정제 / 항전간제)"),
    ("N05", "정신신경용제 (항우울제 / 진정제 / 신경안정제 / 항전간제)"),
    ("N06", "정신신경용제 (항우울제 / 진정제 / 신경안정제 / 항전간제)"),
    ("N07", "정신신경용제 (항우울제 / 진정제 / 신경안정제 / 항전간제)"),
    ("R", "호흡기용제 / 항히스타민제 / 진해거담제"),
    ("A02", "소화기계용제 (위산분비억제제 / 위장운동 / 제산제)"),
    ("A03", "소화기계용제 (위산분비억제제 / 위장운동 / 제산제)"),
    ("A04", "소화기계용제 (위산분비억제제 / 위장운동 / 제산제)"),
    ("A06", "소화기계용제 (위산분비억제제 / 위장운동 / 제산제)"),
    ("A07", "소화기계용제 (위산분비억제제 / 위장운동 / 제산제)"),
    ("A10", "내분비 / 당뇨 / 갑상선 / 골다공증약"),
    ("H", "내분비 / 당뇨 / 갑상선 / 골다공증약"),
    ("M05", "내분비 / 당뇨 / 갑상선 / 골다공증약"),
    ("G03", "내분비 / 당뇨 / 갑상선 / 골다공증약"),
    ("G04", "비뇨생식기계 (전립선비대증 / PDE5 억제제)"),
    ("M04", "통풍치료제"),
]
DEFAULT_CATEGORY = "기타 / 면역억제제"

# 라벨 원문 키워드 → 한글 부작용 표기
ADVERSE_KEYWORDS = [
    (r"bleed|hemorrhag", "출혈 위험 증가"),
    (r"hypoglyc", "저혈당"),
    (r"qt\b|qtc|torsade", "QT 간격 연장 / 부정맥"),
    (r"serotonin syndrome", "세로토닌 증후군"),
    (r"myopathy|rhabdomyolysis", "근병증 / 횡문근융해"),
    (r"hypotension", "저혈압"),
    (r"hyperkal", "고칼륨혈증"),
    (r"respiratory depression|cns depression|sedation", "중추신경·호흡 억제 / 진정"),
    (r"nephrotox|renal (failure|impairment)|kidney", "신기능 저하"),
    (r"hepatotox|liver injury", "간독성"),
    (r"lactic acidosis", "젖산산증"),
    (r"toxicity", "독성 증가"),
]


# ======================= 공통 유틸 =======================
def _now():
    return datetime.now()


def _now_iso():
    return _now().strftime("%Y-%m-%dT%H:%M:%S")


def normalize_query(q):
    q = re.sub(r"\s+", " ", (q or "").strip()).lower()
    return q


def is_ascii_query(q):
    return all(ord(c) < 128 for c in q)


def slugify(name):
    s = "".join(c if c.isalnum() else "_" for c in name.strip().lower())
    return re.sub(r"_+", "_", s).strip("_")


def _drug_matches_query(drug, q):
    q = q.lower()
    if q in (drug.get("name_ko") or "").lower() or q in (drug.get("name_en") or "").lower():
        return True
    return any(q in (b or "").lower() for b in (drug.get("brand_names") or []))


class _Http:
    """요청 수 상한 및 타임아웃이 걸린 JSON GET 헬퍼"""

    def __init__(self, max_requests=MAX_REQUESTS_PER_RUN):
        self.max_requests = max_requests
        self.count = 0
        self.errors = []
        self.last_failed = False

    def get_json(self, url, params=None):
        if self.count >= self.max_requests:
            raise RuntimeError("요청 상한 도달")
        if params:
            url = url + "?" + urllib.parse.urlencode(params, safe=":[]+\"")
        self.count += 1
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.last_failed = False
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:  # openFDA: 검색 결과 없음
                    return None
                if (e.code == 429 or e.code >= 500) and attempt < 2:
                    time.sleep(3 * (attempt + 1))  # 일시 오류 백오프 재시도
                    continue
                self.errors.append(f"HTTP {e.code}: {url[:120]}")
                self.last_failed = True
                return None
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                self.errors.append(f"{type(e).__name__}: {url[:120]}")
                self.last_failed = True
                return None
        return None


# ======================= 1. 미조회 검색어 큐 =======================
def record_unmatched_query(query):
    """사이트에서 검색 결과가 없던 검색어 저장 (중복 시 횟수 증가)"""
    import ddi_data

    norm = normalize_query(query)
    if len(norm) < 2 or len(norm) > 60:
        return {"saved": False, "reason": "검색어 길이는 2~60자여야 합니다."}
    if not re.search(r"[a-z0-9가-힣]", norm):
        return {"saved": False, "reason": "유효하지 않은 검색어입니다."}
    # 서버 기준으로도 이미 존재하면 저장하지 않음
    if any(_drug_matches_query(d, norm) for d in ddi_data.DRUGS):
        return {"saved": False, "reason": "이미 등록된 약물입니다."}

    with _queue_lock:
        queue = load_json(PENDING_FILE, [])
        entry = next((e for e in queue if e.get("normalized") == norm), None)
        now = _now_iso()
        if entry:
            entry["count"] = entry.get("count", 1) + 1
            entry["last_seen"] = now
            # 실패/미해결 항목이 다시 검색되면 재시도 대상으로 복귀
            if entry.get("status") in ("not_found",) and entry.get("attempts", 0) < MAX_ATTEMPTS:
                entry["status"] = "pending"
        else:
            entry = {
                "query": query.strip()[:60],
                "normalized": norm,
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                "status": "pending",
                "attempts": 0,
                "note": "",
                "resolved_drug_ids": [],
            }
            queue.insert(0, entry)
            queue = queue[:2000]
        save_json(PENDING_FILE, queue)
    return {"saved": True, "entry": entry, "next_run": next_run_time().strftime("%Y-%m-%d %H:%M")}


def get_pending_queries():
    return load_json(PENDING_FILE, [])


# ======================= 2. RxNorm / RxClass =======================
def _rx_properties(http, rxcui):
    d = http.get_json(f"{RXNAV}/rxcui/{rxcui}/properties.json")
    return (d or {}).get("properties") or {}


def _rx_related(http, rxcui, ttys):
    d = http.get_json(f"{RXNAV}/rxcui/{rxcui}/related.json", {"tty": " ".join(ttys)})
    out = []
    for grp in ((d or {}).get("relatedGroup") or {}).get("conceptGroup") or []:
        for c in grp.get("conceptProperties") or []:
            out.append({"rxcui": c["rxcui"], "name": c["name"], "tty": c.get("tty", grp.get("tty"))})
    return out


def resolve_ingredients(http, query):
    """검색어(성분명/영문 상품명) → [{'rxcui','name'}] 단일 성분 목록. 실패 시 (None, 사유)"""
    if not is_ascii_query(query):
        return None, "한글 검색어는 RxNorm(영문) 자동 변환이 불가하여 약사 수동 등록이 필요합니다."

    rxcui = None
    d = http.get_json(f"{RXNAV}/rxcui.json", {"name": query, "search": "2"})
    ids = (((d or {}).get("idGroup") or {}).get("rxnormId")) or []
    if ids:
        rxcui = ids[0]
    else:
        d = http.get_json(f"{RXNAV}/approximateTerm.json", {"term": query, "maxEntries": "5", "option": "1"})
        cands = (((d or {}).get("approximateGroup") or {}).get("candidate")) or []
        for c in cands:
            name = c.get("name") or _rx_properties(http, c["rxcui"]).get("name", "")
            ratio = difflib.SequenceMatcher(None, query.lower(), name.lower()).ratio()
            if name and (ratio >= 0.75 or name.lower().startswith(query.lower())):
                rxcui = c["rxcui"]
                break
    if not rxcui:
        return None, "RxNorm에서 일치하는 성분/제품을 찾지 못했습니다 (오타 여부 확인)."

    props = _rx_properties(http, rxcui)
    if props.get("tty") == "IN":
        return [{"rxcui": rxcui, "name": props["name"]}], ""
    ins = [c for c in _rx_related(http, rxcui, ["IN"]) if c.get("tty") == "IN"]
    if not ins:
        return None, "RxNorm 성분(IN) 정보를 찾지 못했습니다."
    return [{"rxcui": c["rxcui"], "name": c["name"]} for c in ins[:3]], ""


def atc_class_of(http, rxcui):
    d = http.get_json(f"{RXNAV}/rxclass/class/byRxcui.json", {"rxcui": rxcui, "relaSource": "ATC"})
    items = (((d or {}).get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []
    for it in items:
        c = it.get("rxclassMinConceptItem") or {}
        if c.get("classId"):
            return c["classId"], c.get("className", "")
    return None, ""


def atc_class_members(http, class_id):
    d = http.get_json(f"{RXNAV}/rxclass/classMembers.json", {"classId": class_id, "relaSource": "ATC", "ttys": "IN"})
    members = (((d or {}).get("drugMemberGroup") or {}).get("drugMember")) or []
    return [{"rxcui": m["minConcept"]["rxcui"], "name": m["minConcept"]["name"]} for m in members]


def epc_classes_of(http, rxcui):
    """FDA 약리학적 분류(EPC, 예: 'GLP-1 Receptor Agonist') — ATC 4단계보다 유사 약물 선별이 정확"""
    d = http.get_json(f"{RXNAV}/rxclass/class/byRxcui.json", {"rxcui": rxcui, "relaSource": "DAILYMED", "relas": "has_epc"})
    items = (((d or {}).get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []
    out = []
    for it in items:
        c = it.get("rxclassMinConceptItem") or {}
        if c.get("classId") and c["classId"] not in [x[0] for x in out]:
            out.append((c["classId"], c.get("className", "")))
    return out


def epc_class_members(http, class_id):
    d = http.get_json(f"{RXNAV}/rxclass/classMembers.json",
                      {"classId": class_id, "relaSource": "DAILYMED", "rela": "has_epc", "ttys": "IN"})
    members = (((d or {}).get("drugMemberGroup") or {}).get("drugMember")) or []
    return [{"rxcui": m["minConcept"]["rxcui"], "name": m["minConcept"]["name"]} for m in members]


def similar_candidates(http, rxcui, atc_id):
    """유사 약물 후보: EPC 동일 분류 우선, 없으면 ATC 4단계 동일 계열"""
    cands = []
    for class_id, _ in epc_classes_of(http, rxcui):
        cands.extend(epc_class_members(http, class_id))
    if not cands and atc_id:
        cands = atc_class_members(http, atc_id)
    seen, out = set(), []
    for c in cands:
        if c["rxcui"] != rxcui and c["name"].lower() not in seen:
            seen.add(c["name"].lower())
            out.append(c)
    return out


def category_from_atc(class_id):
    if not class_id:
        return DEFAULT_CATEGORY
    for prefix, cat in sorted(ATC_CATEGORY_MAP, key=lambda x: -len(x[0])):
        if class_id.upper().startswith(prefix):
            return cat
    return DEFAULT_CATEGORY


# ======================= 3. openFDA 라벨 → DDI 후보 추출 =======================
def fetch_label(http, generic_name):
    params = {
        "search": f'openfda.generic_name:"{generic_name}"',
        "sort": "effective_time:desc",
        "limit": "10",
    }
    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY
    d = http.get_json(OPENFDA_LABEL, params)
    res = [r for r in ((d or {}).get("results") or [])
           if r.get("drug_interactions") or r.get("contraindications")]
    if not res:
        return None
    # 복합제 라벨이 아닌 단일 성분 라벨 우선 (최신 개정순 유지)
    def _n_ingredients(r):
        of = r.get("openfda") or {}
        return len(of.get("substance_name") or of.get("generic_name") or [])
    single = [r for r in res if _n_ingredients(r) == 1]
    return (single or res)[0]


def _label_date(label):
    t = (label or {}).get("effective_time", "")
    return f"{t[:4]}-{t[4:6]}-{t[6:8]}" if len(t) >= 8 else ""


def _sentences(text):
    text = re.sub(r"\s+", " ", text or "")
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z0-9(])", text) if s.strip()]


def _cyp_profile_from_label(label):
    blob = " ".join(" ".join(label.get(k) or []) for k in ("clinical_pharmacology", "pharmacokinetics", "drug_interactions"))
    cyps = sorted(set(m.upper() for m in re.findall(r"\bcyp\s?\d[a-z]\d{1,2}\b", blob, re.I)))
    cyps = [c.replace(" ", "") for c in cyps]
    if "p-glycoprotein" in blob.lower() or "p-gp" in blob.lower():
        cyps.append("P-gp")
    return ("FDA 라벨 언급 대사경로: " + ", ".join(dict.fromkeys(cyps))) if cyps else ""


STRONG_PAT = re.compile(
    r"contraindicated|\bavoid\b|do not (co-?administer|use)|not recommended|fatal|death|life-threatening|serious", re.I)
NEGATION_PAT = re.compile(
    r"\bno (clinically )?(significant|relevant|meaningful|important)\b|no (pharmacokinetic )?(effect|interaction|change)s? |"
    r"did not (significantly )?(alter|affect|change|potentiate|influence|have a)|"
    r"(was|were) not (significantly )?(altered|affected|changed)|no dose adjustment|not expected to|"
    r"not clinically (significant|relevant)|similar in the presence", re.I)


def extract_label_interactions(label, self_drug_id, drugs):
    """라벨 원문에서 DB 내 다른 약물(name_en) 언급 지점을 찾아 {drug_id: info} 반환.

    라벨의 상호작용 표는 '약물명 : Clinical Impact ... Intervention ...' 형태로 이어지므로,
    언급 지점의 문맥 창(window)을 다음 표 행(다른 약물명 + ':' / 'Clinical Impact') 또는
    소제목(예: '7.3 ...')에서 잘라내어 인접 약물의 경고문이 섞이지 않게 합니다.
    """
    texts = []
    for key in ("contraindications", "boxed_warning", "drug_interactions"):
        for txt in label.get(key) or []:
            texts.append((key, re.sub(r"\s+", " ", txt or "")))
    if not texts:
        return {}

    name_to_ids = {}
    for d in drugs:
        if d["id"] == self_drug_id:
            continue
        n = (d.get("name_en") or "").strip().lower()
        if len(n) >= 4:
            name_to_ids.setdefault(n, []).append(d["id"])
    if not name_to_ids:
        return {}
    self_name = next((((d.get("name_en") or "").lower()) for d in drugs if d["id"] == self_drug_id), "")
    all_names = sorted(set(name_to_ids) | ({self_name} if len(self_name) >= 4 else set()), key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in all_names)
    name_re = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(name_to_ids, key=len, reverse=True)) + r")\b", re.I)
    boundary_re = re.compile(r"\b(?:" + alt + r")\b\s*(?::|Clinical Impact)|(?-i:\b\d{1,2}\.\d{1,2}\s+[A-Z][a-z])|Table \d+", re.I)

    found = {}
    for sec, text in texts:
        for m in name_re.finditer(text):
            # 앞쪽 문맥: 같은 문장 시작 또는 직전 경계까지
            back = text[max(0, m.start() - 240):m.start()]
            cut = max(back.rfind(". "), back.rfind("; "))
            for b in boundary_re.finditer(back):
                if b.start() > 0:
                    cut = max(cut, b.start() - 1)
            if cut >= 0:
                back = back[cut + 1:]
            elif m.start() > 240 and " " in back:
                back = "… " + back.split(" ", 1)[1]  # 단어 중간에서 시작하지 않도록
            # 뒤쪽 문맥: 다음 표 행/소제목 직전까지 (최대 420자)
            fwd = text[m.end():m.end() + 420]
            nb = boundary_re.search(fwd, 1)
            if nb:
                fwd = fwd[:nb.start()]
            elif m.end() + 420 < len(text) and " " in fwd:
                fwd = fwd.rsplit(" ", 1)[0] + " …"
            window = (back + m.group(0) + fwd).strip()
            if re.search(r"hypersensitivity|allerg", back, re.I):
                continue  # 성분 과민반응 금기 문구는 약물 상호작용이 아님
            contra = sec == "contraindications" or "contraindicated" in window.lower()
            strong = contra or sec == "boxed_warning" or bool(STRONG_PAT.search(window))
            # 라벨 7장/12장에는 '상호작용 없음' 연구 결과도 다수 기재됨 → 부정문만 있고
            # 강한 경고·위해반응 키워드가 없는 문맥은 상호작용 후보에서 제외
            if (not strong and NEGATION_PAT.search(window)
                    and not any(re.search(p, window, re.I) for p, _ in ADVERSE_KEYWORDS)):
                continue
            for did in name_to_ids[m.group(1).lower()]:
                info = found.setdefault(did, {"sentences": [], "contra_mentioned": False,
                                              "severity": "MODERATE", "joined": ""})
                if len(info["sentences"]) < 3 and window not in info["sentences"]:
                    info["sentences"].append(window)
                    info["joined"] = (info["joined"] + " " + window.lower()).strip()
                info["contra_mentioned"] = info["contra_mentioned"] or contra
                if strong:
                    info["severity"] = "MAJOR"
    return found


def _product_note(label):
    of = (label or {}).get("openfda") or {}
    brand = (of.get("brand_name") or [""])[0]
    n_ing = len(of.get("substance_name") or of.get("generic_name") or [])
    if not brand:
        return ""
    return f" · 제품: {brand}" + (" (복합제 라벨)" if n_ing > 1 else "")


def build_auto_rule(drug_a, drug_b, info, label, rule_id):
    sev = info["severity"]
    if info["contra_mentioned"]:
        sev_ko = "자동 수집·미검증 (FDA 라벨 병용금기 언급)"
    elif sev == "MAJOR":
        sev_ko = "자동 수집·미검증 (중대한 위험 추정)"
    else:
        sev_ko = "자동 수집·미검증 (병용 주의 추정)"

    excerpt = " … ".join(info["sentences"])
    if len(excerpt) > 700:
        excerpt = excerpt[:700].rsplit(" ", 1)[0] + " …"

    adverse = []
    for pat, ko in ADVERSE_KEYWORDS:
        if re.search(pat, info["joined"], re.I) and ko not in adverse:
            adverse.append(ko)
    if not adverse:
        adverse = ["FDA 라벨 원문 참조 (구체적 위해반응 미기재)"]

    actions = []
    j = info["joined"]
    if info["contra_mentioned"]:
        actions.append("FDA 라벨에 병용금기(Contraindicated)로 언급됨 — 국내 DUR 병용금기 해당 여부를 반드시 확인하십시오.")
    if re.search(r"\bavoid\b|not recommended|do not", j):
        actions.append("라벨: 병용 회피 권고.")
    if re.search(r"dose (adjust|reduc)|reduce the dose|lower dose|dosage (adjust|reduc)", j):
        actions.append("라벨: 용량 조절 권고.")
    if re.search(r"monitor", j):
        actions.append("라벨: 임상 모니터링 권고.")
    actions.append("본 항목은 FDA 허가사항(라벨) 원문에서 자동 추출된 후보 상호작용으로, 약사 검증 전에는 참고용으로만 활용하십시오.")

    set_id = label.get("set_id", "")
    return {
        "id": rule_id,
        "drugs": [drug_a["id"], drug_b["id"]],
        "drug_a_id": drug_a["id"],
        "drug_b_id": drug_b["id"],
        "severity": sev,
        "severity_ko": sev_ko,
        "title": f"{drug_a['name_ko']} + {drug_b['name_ko']} (FDA 라벨 자동 수집)",
        # 라벨 원문(예: 'CrCl <30')은 화면에서 innerHTML 로 렌더링되므로 HTML 이스케이프
        "mechanism": html.escape(f"[FDA 라벨 원문 발췌 · {drug_a['name_en']} 허가사항{_product_note(label)}] {excerpt}", quote=False),
        "adverse_reactions": [html.escape(a, quote=False) for a in adverse],
        "clinical_action": html.escape(" ".join(actions), quote=False),
        "hospital_department": "",
        "is_recent_sci": False,
        "auto_imported": True,
        "needs_review": True,
        "source": "openFDA Drug Label (U.S. FDA SPL)",
        "source_url": f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}" if set_id else "",
        "label_effective_date": _label_date(label),
        "added_at": _now_iso(),
        "updated_at": _now_iso(),
    }


# ======================= 4. 일일 배치 본체 =======================
class _Batch:
    def __init__(self, http):
        self.http = http
        self.drugs = load_json(DRUGS_FILE, [])
        self.rules = load_json(RULES_FILE, [])
        self.drug_ids = {d["id"] for d in self.drugs}
        self.name_index = {(d.get("name_en") or "").strip().lower(): d for d in self.drugs}
        self.pair_index = {tuple(sorted(r.get("drugs", [])[:2])): r for r in self.rules}
        self.new_drugs = []
        self.new_rules = []
        self.updated_rules = []
        self.linked_aliases = []
        self.rule_seq = 0
        self._rule_prefix = "DDI-AUTO-" + _now().strftime("%Y%m%d") + "-"
        existing = [r["id"] for r in self.rules if str(r.get("id", "")).startswith(self._rule_prefix)]
        for rid in existing:
            try:
                self.rule_seq = max(self.rule_seq, int(rid.rsplit("-", 1)[1]))
            except ValueError:
                pass

    def next_rule_id(self):
        self.rule_seq += 1
        return f"{self._rule_prefix}{self.rule_seq:04d}"

    def find_by_name(self, name):
        return self.name_index.get(name.strip().lower())

    def add_drug(self, ing, origin_query, similar_to=None, brand_hint=None, require_label=False):
        """삽입 전용: 같은 영문명/ID가 있으면 등록하지 않고 기존 레코드 반환.
        require_label=True 이면 현행 FDA 라벨이 없는(미시판/철수) 약물은 등록하지 않음."""
        existing = self.find_by_name(ing["name"])
        if existing:
            return existing, False
        did = slugify(ing["name"])
        if did in self.drug_ids:
            return next(d for d in self.drugs if d["id"] == did), False

        label = fetch_label(self.http, ing["name"])
        if require_label and not label:
            return None, False
        class_id, class_name = atc_class_of(self.http, ing["rxcui"])
        epcs = epc_classes_of(self.http, ing["rxcui"])
        brands = [b["name"] for b in _rx_related(self.http, ing["rxcui"], ["BN"]) if b.get("tty") == "BN"][:6]
        if brand_hint and brand_hint.lower() not in [b.lower() for b in brands]:
            brands.insert(0, brand_hint)
        name_en = ing["name"][:1].upper() + ing["name"][1:]
        drug = {
            "id": did,
            "name_ko": name_en,
            "name_en": name_en,
            "category": category_from_atc(class_id),
            "brand_names": brands,
            "class": " / ".join([n for _, n in epcs] + ([f"ATC {class_id}"] if class_id else [])) or "분류 미확인",
            "cyp_profile": _cyp_profile_from_label(label) if label else "",
            "auto_imported": True,
            "needs_review": True,
            "name_ko_pending": True,
            "rxcui": ing["rxcui"],
            "atc_class_id": class_id or "",
            "origin_query": origin_query,
            "similar_to": similar_to or "",
            "source": "NLM RxNorm / RxClass(ATC)" + (" + openFDA Label" if label else ""),
            "added_at": _now_iso(),
        }
        self.drugs.append(drug)
        self.drug_ids.add(did)
        self.name_index[name_en.lower()] = drug
        self.new_drugs.append(drug)
        if label:
            self.apply_label(drug, label)
        return drug, True

    def apply_label(self, drug, label):
        """라벨에서 DB 내 약물과의 상호작용 후보를 추출해 규칙 등록/갱신 (큐레이션 규칙은 보존)"""
        found = extract_label_interactions(label, drug["id"], self.drugs)
        lab_date = _label_date(label)
        for other_id, info in found.items():
            other = next((d for d in self.drugs if d["id"] == other_id), None)
            if not other:
                continue
            key = tuple(sorted([drug["id"], other_id]))
            existing = self.pair_index.get(key)
            if existing and not existing.get("auto_imported"):
                continue  # 수작업 큐레이션 규칙 우선
            if existing:
                if (existing.get("label_effective_date") or "") >= lab_date:
                    continue
                rule = build_auto_rule(drug, other, info, label, existing["id"])
                rule["added_at"] = existing.get("added_at", rule["added_at"])
                existing.clear()
                existing.update(rule)
                self.updated_rules.append(existing)
            else:
                rule = build_auto_rule(drug, other, info, label, self.next_rule_id())
                self.rules.append(rule)
                self.pair_index[key] = rule
                self.new_rules.append(rule)

    # ---- 단계 A: 대기 검색어 처리 ----
    def process_pending(self, max_queries):
        with _queue_lock:
            queue = load_json(PENDING_FILE, [])
        targets = [e for e in queue if e.get("status") == "pending" and e.get("attempts", 0) < MAX_ATTEMPTS]
        targets.sort(key=lambda e: (-e.get("count", 1), e.get("first_seen", "")))
        results = {}
        for e in targets[:max_queries]:
            q = e["normalized"]
            res = {"attempts": e.get("attempts", 0) + 1, "last_attempt": _now_iso()}
            try:
                # 그 사이 수동 등록되었는지 확인
                if any(_drug_matches_query(d, q) for d in self.drugs):
                    res.update(status="exists", note="이미 DB에 등록되어 있습니다.")
                    results[q] = res
                    continue
                ings, reason = resolve_ingredients(self.http, q)
                if not ings:
                    status = "needs_manual" if not is_ascii_query(q) else "not_found"
                    res.update(status=status, note=reason)
                    results[q] = res
                    continue
                ids = []
                for ing in ings:
                    is_brand = ing["name"].lower() != q
                    existing = self.find_by_name(ing["name"])
                    if existing:
                        # 영문 상품명 검색이었다면 기존 약물에 상품명 별칭만 추가 (기존 데이터는 변경하지 않음)
                        if is_brand and q not in [b.lower() for b in existing.get("brand_names") or []]:
                            existing.setdefault("brand_names", []).append(e["query"])
                            self.linked_aliases.append({"drug_id": existing["id"], "alias": e["query"]})
                        ids.append(existing["id"])
                        main = existing
                    else:
                        main, _ = self.add_drug(ing, origin_query=e["query"], brand_hint=e["query"] if is_brand else None)
                        ids.append(main["id"])
                    # 유사 약물 (FDA EPC 동일 약리 분류 우선, 없으면 ATC 4단계 동일 계열)
                    atc_id = main.get("atc_class_id") or atc_class_of(self.http, ing["rxcui"])[0]
                    added = 0
                    for m in similar_candidates(self.http, ing["rxcui"], atc_id):
                        if added >= MAX_SIMILAR_PER_DRUG:
                            break
                        if self.find_by_name(m["name"]):
                            continue
                        _, created = self.add_drug(m, origin_query=e["query"], similar_to=main["id"],
                                                   require_label=True)
                        if created:
                            added += 1
                res.update(status="resolved", resolved_drug_ids=ids,
                           note=f"{', '.join(i['name'] for i in ings)} 등록/연결 완료")
            except RuntimeError as ex:  # 요청 상한
                res.update(status="pending", note=str(ex))
                results[q] = res
                break
            except Exception as ex:
                res.update(status="pending" if res["attempts"] < MAX_ATTEMPTS else "not_found",
                           note=f"처리 오류: {type(ex).__name__}: {ex}")
            results[q] = res

        if results:
            with _queue_lock:
                queue = load_json(PENDING_FILE, [])
                for entry in queue:
                    r = results.get(entry.get("normalized"))
                    if r:
                        entry.update(r)
                save_json(PENDING_FILE, queue)
        return results

    # ---- 단계 B: 최근 개정 FDA 라벨 반영 (최신순) ----
    def refresh_recent_labels(self, since_date):
        today = _now().strftime("%Y%m%d")
        since = since_date.strftime("%Y%m%d")
        processed = 0
        skip = 0
        matched = 0
        complete = True
        while processed < MAX_RECENT_LABELS:
            params = {
                "search": f"effective_time:[{since}+TO+{today}]+AND+_exists_:drug_interactions",
                "sort": "effective_time:desc",
                "limit": "100",
                "skip": str(skip),
            }
            if OPENFDA_API_KEY:
                params["api_key"] = OPENFDA_API_KEY
            d = self.http.get_json(OPENFDA_LABEL, params)
            results = (d or {}).get("results") or []
            if not results:
                complete = not self.http.last_failed  # 네트워크/서버 오류로 중단된 경우 미완료
                break
            for label in results:
                processed += 1
                generics = (label.get("openfda") or {}).get("generic_name") or []
                if len(generics) != 1:
                    continue
                g = generics[0].strip().lower()
                drug = self.find_by_name(g)
                if not drug:
                    # 염(salt) 표기 제거: "amlodipine besylate" → "amlodipine"
                    drug = next((dd for n, dd in self.name_index.items() if n and len(n) >= 4 and g.startswith(n + " ")), None)
                if not drug:
                    continue
                matched += 1
                self.apply_label(drug, label)
            if len(results) < 100:
                break
            skip += 100
        return {"labels_scanned": processed, "labels_matched": matched, "complete": complete}

    def commit(self):
        """변경분을 JSON 저장 및 메모리(ddi_data) 반영"""
        import ddi_data
        if not (self.new_drugs or self.new_rules or self.updated_rules or self.linked_aliases):
            return False
        with data_store.DATA_LOCK:
            # 배치 도중 HTTP로 수동 추가된 항목을 잃지 않도록 최신 파일과 병합
            cur_drugs = load_json(DRUGS_FILE, [])
            cur_ids = {d["id"] for d in cur_drugs}
            alias_map = {}
            for a in self.linked_aliases:
                alias_map.setdefault(a["drug_id"], []).append(a["alias"])
            for d in cur_drugs:
                for alias in alias_map.get(d["id"], []):
                    if alias not in d.setdefault("brand_names", []):
                        d["brand_names"].append(alias)
            cur_drugs.extend(d for d in self.new_drugs if d["id"] not in cur_ids)

            cur_rules = load_json(RULES_FILE, [])
            by_id = {r.get("id"): r for r in cur_rules}
            cur_pairs = {tuple(sorted(r.get("drugs", [])[:2])) for r in cur_rules}
            for r in self.updated_rules:
                tgt = by_id.get(r["id"])
                if tgt is not None and tgt.get("auto_imported"):
                    tgt.clear()
                    tgt.update(r)
            for r in self.new_rules:
                if tuple(sorted(r["drugs"])) not in cur_pairs:
                    cur_rules.append(r)

            save_json(DRUGS_FILE, cur_drugs)
            save_json(RULES_FILE, cur_rules)
            ddi_data.DRUGS.clear()
            ddi_data.DRUGS.extend(cur_drugs)
            ddi_data.DDI_RULES.clear()
            ddi_data.DDI_RULES.extend(cur_rules)
        return True


def _load_state():
    return load_json(STATE_FILE, {}) if os.path.exists(STATE_FILE) else {}


def next_run_time():
    now = _now()
    state = _load_state()
    today_run = now.replace(hour=UPDATE_HOUR, minute=0, second=0, microsecond=0)
    if state.get("last_run_date") == now.strftime("%Y-%m-%d"):
        return today_run + timedelta(days=1)
    if now < today_run:
        return today_run
    return now + timedelta(minutes=5)  # 오늘 미실행 → 스케줄러가 곧 보충 실행


def run_daily_update(trigger="schedule", max_queries=None, include_labels=True, git_sync=True):
    """일일 자동 업데이트 실행. 이미 실행 중이면 즉시 반환."""
    if not _run_lock.acquire(blocking=False):
        return {"status": "busy", "message": "자동 업데이트가 이미 실행 중입니다."}
    _run_status.update(running=True, started_at=_now_iso(), trigger=trigger)
    started = time.time()
    summary = {"started_at": _now_iso(), "trigger": trigger}
    try:
        http = _Http()
        batch = _Batch(http)
        state = _load_state()

        pending_results = batch.process_pending(max_queries if max_queries is not None else MAX_QUERIES_PER_RUN)

        label_stats = {}
        if include_labels:
            # openFDA 는 주 단위로 갱신되며 개정 라벨이 늦게 공개되는 경우가 많으므로,
            # 직전 실행일로부터 LABEL_OVERLAP_DAYS 만큼 겹쳐 조회합니다.
            # (이미 반영한 라벨 개정일보다 새로운 경우에만 규칙을 갱신하므로 중복 반영 없음)
            last = state.get("last_label_refresh_date")
            try:
                base = datetime.strptime(last, "%Y-%m-%d") if last else _now() - timedelta(days=FIRST_RUN_LABEL_DAYS - LABEL_OVERLAP_DAYS)
            except ValueError:
                base = _now()
            since = base - timedelta(days=LABEL_OVERLAP_DAYS)
            try:
                label_stats = batch.refresh_recent_labels(since)
                if label_stats.get("complete"):
                    # 중간 실패 시 기준일을 전진시키지 않아 다음 실행에서 누락분을 다시 조회
                    state["last_label_refresh_date"] = _now().strftime("%Y-%m-%d")
            except RuntimeError as ex:
                label_stats = {"error": str(ex)}

        changed = batch.commit()

        summary.update({
            "finished_at": _now_iso(),
            "duration_sec": round(time.time() - started, 1),
            "queries_processed": len(pending_results),
            "queries_resolved": sum(1 for r in pending_results.values() if r.get("status") == "resolved"),
            "new_drugs": [{"id": d["id"], "name_en": d["name_en"], "similar_to": d.get("similar_to", "")} for d in batch.new_drugs],
            "new_drugs_count": len(batch.new_drugs),
            "new_rules": len(batch.new_rules),
            "updated_rules": len(batch.updated_rules),
            "linked_aliases": batch.linked_aliases,
            "label_refresh": label_stats,
            "http_requests": http.count,
            "errors": http.errors[:20],
            "status": "success",
        })

        state["last_run_date"] = _now().strftime("%Y-%m-%d")
        state["last_run_at"] = summary["finished_at"]
        state["last_summary"] = {k: v for k, v in summary.items() if k not in ("new_drugs", "errors", "linked_aliases")}
        save_json(STATE_FILE, state)

        logs = load_json(UPDATE_LOG_FILE, [])
        logs.insert(0, summary)
        save_json(UPDATE_LOG_FILE, logs[:60])

        if git_sync:
            msg = f"일일 자동 업데이트: 신규 의약품 {len(batch.new_drugs)}종, 신규 DDI {len(batch.new_rules)}건, 갱신 {len(batch.updated_rules)}건"
            data_store.queue_git_sync(msg)
        print(f"[AutoUpdate] 완료: {summary['queries_processed']} 검색어, 신규 약물 {len(batch.new_drugs)}, "
              f"신규 규칙 {len(batch.new_rules)}, 갱신 {len(batch.updated_rules)} (changed={changed})")
        return summary
    except Exception as ex:
        summary.update(status="error", error=f"{type(ex).__name__}: {ex}", finished_at=_now_iso())
        print(f"[AutoUpdate] 실패: {summary['error']}")
        logs = load_json(UPDATE_LOG_FILE, [])
        logs.insert(0, summary)
        save_json(UPDATE_LOG_FILE, logs[:60])
        return summary
    finally:
        _run_status.update(running=False)
        _run_lock.release()


def run_in_background(trigger="manual"):
    if _run_status["running"]:
        return False
    threading.Thread(target=run_daily_update, kwargs={"trigger": trigger}, daemon=True).start()
    return True


def get_status():
    state = _load_state()
    queue = load_json(PENDING_FILE, [])
    counts = {}
    for e in queue:
        counts[e.get("status", "pending")] = counts.get(e.get("status", "pending"), 0) + 1
    logs = load_json(UPDATE_LOG_FILE, [])
    return {
        "enabled": os.environ.get("DATA_AUTO_UPDATE", "1") != "0",
        "running": _run_status["running"],
        "update_hour": UPDATE_HOUR,
        "next_run": next_run_time().strftime("%Y-%m-%d %H:%M"),
        "last_run_at": state.get("last_run_at"),
        "last_summary": state.get("last_summary"),
        "queue_counts": counts,
        "queue_total": len(queue),
        "recent_logs": logs[:5],
    }


# ======================= 5. 스케줄러 =======================
def _scheduler_loop():
    time.sleep(15)  # 서버 기동 후 대기
    while True:
        try:
            now = _now()
            state = _load_state()
            today = now.strftime("%Y-%m-%d")
            if now.hour >= UPDATE_HOUR and state.get("last_run_date") != today:
                run_daily_update(trigger="schedule")
        except Exception as ex:
            print(f"[AutoUpdate] 스케줄러 오류: {ex}")
        time.sleep(300)


def start_scheduler():
    if os.environ.get("DATA_AUTO_UPDATE", "1") == "0":
        print("[AutoUpdate] DATA_AUTO_UPDATE=0 — 일일 자동 업데이트 비활성화")
        return None
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="ddi-auto-update")
    t.start()
    print(f"[AutoUpdate] 일일 자동 업데이트 스케줄러 가동 (매일 {UPDATE_HOUR:02d}:00 이후 1회, 미실행 시 기동 직후 보충 실행)")
    return t


if __name__ == "__main__":
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Pharm-DDI 일일 자동 업데이트")
    ap.add_argument("--max-queries", type=int, default=None)
    ap.add_argument("--no-labels", action="store_true", help="최근 개정 FDA 라벨 반영 단계 생략")
    ap.add_argument("--git", action="store_true", help="완료 후 Git 자동 동기화 실행")
    ap.add_argument("--since-days", type=int, default=None, help="라벨 반영 기간(일)을 강제 지정")
    args = ap.parse_args()
    if args.since_days is not None:
        st = _load_state()
        st["last_label_refresh_date"] = (_now() - timedelta(days=args.since_days)).strftime("%Y-%m-%d")
        save_json(STATE_FILE, st)
    out = run_daily_update(trigger="cli", max_queries=args.max_queries, include_labels=not args.no_labels, git_sync=args.git)
    print(json.dumps({k: v for k, v in out.items() if k != "new_drugs"}, ensure_ascii=False, indent=2))
    print("신규 의약품:", ", ".join(d["name_en"] for d in out.get("new_drugs", [])) or "-")
    if args.git:
        time.sleep(3)
        if data_store._git_thread:
            data_store._git_thread.join(timeout=60)
