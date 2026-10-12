# -*- coding: utf-8 -*-
"""
Git-Backed Continuous Data Accumulation Engine (data_store.py)
Stores drugs, DDI rules, patients, visits, and clinical memos in structured JSON files
inside the git repository, and automatically commits and pushes changes to GitHub.
"""

import os
import json
import sqlite3
import subprocess
import threading
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "pharmacy.db"))

os.makedirs(DATA_DIR, exist_ok=True)

DRUGS_FILE = os.path.join(DATA_DIR, "drugs.json")
RULES_FILE = os.path.join(DATA_DIR, "rules.json")
PATIENTS_FILE = os.path.join(DATA_DIR, "patients.json")
VISITS_FILE = os.path.join(DATA_DIR, "visits.json")
MEMOS_FILE = os.path.join(DATA_DIR, "memos.json")
COMMENTS_FILE = os.path.join(DATA_DIR, "comments.json")
SYNC_LOG_FILE = os.path.join(DATA_DIR, "sync_log.json")

# In-memory sync status
_sync_lock = threading.Lock()
_git_queue = []
_git_thread = None
_sync_status = {
    "is_syncing": False,
    "last_sync_time": None,
    "last_commit_hash": None,
    "last_commit_msg": None,
    "status": "ready",
    "remote_url": "https://github.com/ralf-kang/Pharm-DDI",
    "total_synced_items": 0
}

def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {path}: {e}")
    return default if default is not None else []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ================= 1. 초기 데이터 저장소 동기화 =================
def init_data_store():
    """서버 시작 시 data/*.json 및 SQLite 동기화"""
    import ddi_data

    # 1. drugs.json
    if not os.path.exists(DRUGS_FILE) or os.path.getsize(DRUGS_FILE) == 0:
        save_json(DRUGS_FILE, ddi_data.DRUGS)
        print(f"[DataStore] Initialized {DRUGS_FILE} with {len(ddi_data.DRUGS)} drugs.")
    else:
        # Load from JSON to memory
        loaded_drugs = load_json(DRUGS_FILE, [])
        if len(loaded_drugs) >= len(ddi_data.DRUGS):
            ddi_data.DRUGS.clear()
            ddi_data.DRUGS.extend(loaded_drugs)
            print(f"[DataStore] Loaded {len(loaded_drugs)} drugs from git repository.")

    # 2. rules.json
    if not os.path.exists(RULES_FILE) or os.path.getsize(RULES_FILE) == 0:
        save_json(RULES_FILE, ddi_data.DDI_RULES)
        print(f"[DataStore] Initialized {RULES_FILE} with {len(ddi_data.DDI_RULES)} rules.")
    else:
        loaded_rules = load_json(RULES_FILE, [])
        if len(loaded_rules) >= len(ddi_data.DDI_RULES):
            ddi_data.DDI_RULES.clear()
            ddi_data.DDI_RULES.extend(loaded_rules)
            print(f"[DataStore] Loaded {len(loaded_rules)} DDI rules from git repository.")

    # 3. Export DB tables to JSON if JSON doesn't exist
    sync_db_to_json(commit_msg=None)

    # 4. Read last commit info
    update_git_head_status()

def sync_db_to_json(commit_msg="데이터베이스 동기화"):
    """SQLite의 환자/상담일지/메모/코멘트를 Git JSON 파일로 덤프"""
    if not os.path.exists(DB_PATH):
        return

    conn = get_db_conn()
    cur = conn.cursor()

    try:
        cur.execute("SELECT * FROM patients ORDER BY id ASC")
        patients = [dict(r) for r in cur.fetchall()]
        save_json(PATIENTS_FILE, patients)

        cur.execute("SELECT * FROM patient_visits ORDER BY id ASC")
        visits = [dict(r) for r in cur.fetchall()]
        save_json(VISITS_FILE, visits)

        cur.execute("SELECT * FROM pharmacist_memos ORDER BY id ASC")
        memos = [dict(r) for r in cur.fetchall()]
        save_json(MEMOS_FILE, memos)

        cur.execute("SELECT * FROM memo_comments ORDER BY id ASC")
        comments = [dict(r) for r in cur.fetchall()]
        save_json(COMMENTS_FILE, comments)

        if commit_msg:
            queue_git_sync(commit_msg)
    except Exception as e:
        print(f"[DataStore] Error syncing DB to JSON: {e}")
    finally:
        conn.close()

def sync_json_to_db():
    """Git JSON 파일에서 SQLite로 복원/동기화"""
    if not os.path.exists(PATIENTS_FILE):
        return

    patients = load_json(PATIENTS_FILE, [])
    visits = load_json(VISITS_FILE, [])
    memos = load_json(MEMOS_FILE, [])
    comments = load_json(COMMENTS_FILE, [])

    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if patients:
            cur.execute("DELETE FROM patients")
            for p in patients:
                cur.execute("""
                    INSERT OR REPLACE INTO patients 
                    (id, chart_no, name, birth_year, gender, phone, chronic_conditions, allergies, regular_meds, special_notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (p.get("id"), p.get("chart_no"), p.get("name"), p.get("birth_year"), p.get("gender"), p.get("phone"),
                      p.get("chronic_conditions"), p.get("allergies"), p.get("regular_meds"), p.get("special_notes"),
                      p.get("created_at"), p.get("updated_at")))

        if visits:
            cur.execute("DELETE FROM patient_visits")
            for v in visits:
                cur.execute("""
                    INSERT OR REPLACE INTO patient_visits
                    (id, patient_id, visit_date, hospital_name, hospital_dept, prescribed_drugs, ddi_risk_summary, counseling_notes, pharmacist_name, prescription_image, ocr_raw_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (v.get("id"), v.get("patient_id"), v.get("visit_date"), v.get("hospital_name"), v.get("hospital_dept"),
                      v.get("prescribed_drugs"), v.get("ddi_risk_summary"), v.get("counseling_notes"), v.get("pharmacist_name"),
                      v.get("prescription_image"), v.get("ocr_raw_text"), v.get("created_at")))

        if memos:
            cur.execute("DELETE FROM pharmacist_memos")
            for m in memos:
                cur.execute("""
                    INSERT OR REPLACE INTO pharmacist_memos
                    (id, title, category, target_drugs, hospital_dept, content, author_name, tags, is_pinned, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (m.get("id"), m.get("title"), m.get("category"), m.get("target_drugs"), m.get("hospital_dept"),
                      m.get("content"), m.get("author_name", "대표약사"), m.get("tags"), m.get("is_pinned", 0),
                      m.get("created_at"), m.get("updated_at")))

        if comments:
            cur.execute("DELETE FROM memo_comments")
            for c in comments:
                cur.execute("""
                    INSERT OR REPLACE INTO memo_comments
                    (id, memo_id, author_name, comment_text, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (c.get("id"), c.get("memo_id"), c.get("author_name"), c.get("comment_text"), c.get("created_at")))

        conn.commit()
    except Exception as e:
        print(f"[DataStore] Error syncing JSON to DB: {e}")
    finally:
        conn.close()

# ================= 2. DDInter 지식 축적 (신규 의약품 / DDI 규칙) =================
def add_new_drug(drug_data):
    """신규 의약품을 Git 저장소 data/drugs.json 및 ddi_data에 즉시 추가"""
    import ddi_data
    drugs = load_json(DRUGS_FILE, [])

    did = drug_data.get("id", "").strip().lower()
    if not did:
        name_en = drug_data.get("name_en", "").strip().lower()
        if name_en:
            did = "".join(c if c.isalnum() else "_" for c in name_en).strip("_")
        else:
            name_ko = drug_data.get("name_ko", "").strip()
            did = f"drug_{int(time.time())}"

    drug_data["id"] = did

    # brand_names normalization
    b_names = drug_data.get("brand_names", [])
    if isinstance(b_names, str):
        b_names = [b.strip() for b in b_names.replace(";", ",").split(",") if b.strip()]
    drug_data["brand_names"] = b_names

    existing = next((d for d in drugs if d["id"] == did), None)
    if existing:
        existing.update(drug_data)
        action = "업데이트"
    else:
        drugs.append(drug_data)
        action = "추가"

    save_json(DRUGS_FILE, drugs)

    # 메모리 갱신
    ddi_data.DRUGS.clear()
    ddi_data.DRUGS.extend(drugs)

    # Git auto-sync
    commit_msg = f"의약품 지식 축적: {drug_data.get('name_ko')} ({drug_data.get('name_en')}) {action}"
    queue_git_sync(commit_msg)
    return {"status": "success", "action": action, "drug": drug_data, "total_drugs": len(drugs)}

def add_new_rule(rule_data):
    """신규 DDI 상호작용 규칙을 Git 저장소 data/rules.json 및 ddi_data에 즉시 추가"""
    import ddi_data
    rules = load_json(RULES_FILE, [])

    rid = rule_data.get("id")
    if not rid:
        # 새 ID 자동 발급
        max_num = 1
        for r in rules:
            if r.get("id", "").startswith("DDI-EXP-"):
                try:
                    num = int(r["id"].replace("DDI-EXP-", ""))
                    if num >= max_num:
                        max_num = num + 1
                except ValueError:
                    pass
        rid = f"DDI-EXP-{max_num:04d}"
        rule_data["id"] = rid

    # Drug A, B 및 drugs 리스트 정규화
    if "drugs" not in rule_data or not rule_data["drugs"]:
        drug_a = rule_data.get("drug_a_id", "")
        drug_b = rule_data.get("drug_b_id", "")
        if drug_a and drug_b:
            rule_data["drugs"] = [drug_a, drug_b]
    elif len(rule_data.get("drugs", [])) >= 2:
        rule_data["drug_a_id"] = rule_data["drugs"][0]
        rule_data["drug_b_id"] = rule_data["drugs"][1]

    # Normalization
    raw_adv = rule_data.get("adverse_reactions", [])
    if isinstance(raw_adv, str):
        rule_data["adverse_reactions"] = [a.strip() for a in raw_adv.split(",") if a.strip()]

    sev = rule_data.get("severity", "MAJOR").upper()
    if sev not in ["CONTRAINDICATED", "MAJOR", "MODERATE"]:
        sev = "MAJOR"
    rule_data["severity"] = sev

    sev_ko_map = {
        "CONTRAINDICATED": "병용 금기",
        "MAJOR": "중대한 위험",
        "MODERATE": "병용 주의"
    }
    rule_data["severity_ko"] = rule_data.get("severity_ko") or sev_ko_map.get(sev, "중대한 위험")

    # 중복 검사
    rule_drugs = sorted(rule_data.get("drugs", []))
    existing = next((r for r in rules if sorted(r.get("drugs", [])) == rule_drugs), None)
    if existing:
        existing.update(rule_data)
        action = "업데이트"
    else:
        rules.append(rule_data)
        action = "추가"

    save_json(RULES_FILE, rules)

    # 메모리 갱신
    ddi_data.DDI_RULES.clear()
    ddi_data.DDI_RULES.extend(rules)

    # Git auto-sync
    commit_msg = f"DDI 상호작용 규칙 축적: {rule_data.get('title')} ({action})"
    queue_git_sync(commit_msg)
    return {"status": "success", "action": action, "rule": rule_data, "total_rules": len(rules)}

# ================= 3. Git 비동기 자동 동기화 엔진 =================
def queue_git_sync(commit_msg):
    """Git 동기화 큐에 작업 등록 및 백그라운드 워커 트리거"""
    global _git_queue, _git_thread
    with _sync_lock:
        _git_queue.append({
            "message": commit_msg,
            "timestamp": datetime.now().isoformat()
        })
        _sync_status["status"] = "pending"
        _sync_status["last_commit_msg"] = commit_msg

        if _git_thread is None or not _git_thread.is_alive():
            _git_thread = threading.Thread(target=_process_git_queue, daemon=True)
            _git_thread.start()

def _process_git_queue():
    """백그라운드에서 Git add, commit, push 일괄 처리"""
    global _git_queue
    # 2초간 디바운스 (연속 요청 취합)
    time.sleep(2.0)

    with _sync_lock:
        if not _git_queue:
            return
        messages = [q["message"] for q in _git_queue]
        _git_queue.clear()
        combined_msg = " & ".join(messages[:3])
        if len(messages) > 3:
            combined_msg += f" 외 {len(messages) - 3}건"
        _sync_status["is_syncing"] = True
        _sync_status["status"] = "syncing"

    try:
        # 1. git add data/
        subprocess.run(["git", "add", "data/"], cwd=BASE_DIR, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")

        # 변경사항 있는지 확인
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not status_res.stdout.strip():
            print("[DataStore] No changes detected in data/ to commit.")
            with _sync_lock:
                _sync_status["is_syncing"] = False
                _sync_status["status"] = "synced"
            return

        # 2. git commit
        full_commit_msg = f"[Pharm-DDI Data 축적] {combined_msg}"
        subprocess.run(["git", "commit", "-m", full_commit_msg], cwd=BASE_DIR, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")

        # 3. git push origin main
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"[DataStore] Successfully pushed to GitHub: {full_commit_msg}")

        # 4. Update status
        update_git_head_status()
        with _sync_lock:
            _sync_status["is_syncing"] = False
            _sync_status["status"] = "synced"
            _sync_status["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Log to sync_log.json
            log_entry = {
                "timestamp": _sync_status["last_sync_time"],
                "commit_hash": _sync_status["last_commit_hash"],
                "message": full_commit_msg,
                "status": "success"
            }
            logs = load_json(SYNC_LOG_FILE, [])
            logs.insert(0, log_entry)
            save_json(SYNC_LOG_FILE, logs[:50]) # keep last 50 logs

    except Exception as e:
        print(f"[DataStore] Git sync failed: {e}")
        with _sync_lock:
            _sync_status["is_syncing"] = False
            _sync_status["status"] = "error"
            _sync_status["error_message"] = str(e)

def update_git_head_status():
    """현재 Git HEAD 커밋 해시 조회"""
    try:
        rev_res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if rev_res.returncode == 0:
            _sync_status["last_commit_hash"] = rev_res.stdout.strip()
    except Exception:
        pass

def get_git_sync_status():
    """현재 동기화 상태 및 최근 커밋 내역 반환"""
    update_git_head_status()
    with _sync_lock:
        status_copy = dict(_sync_status)
        drugs = load_json(DRUGS_FILE, [])
        rules = load_json(RULES_FILE, [])
        status_copy["total_drugs"] = len(drugs)
        status_copy["total_rules"] = len(rules)
        status_copy["branch"] = "main"
        status_copy["commit_hash"] = _sync_status.get("last_commit_hash", "4e0ed1a")
        status_copy["commit_time"] = _sync_status.get("last_sync_time")

        # Git 최근 커밋 내역 조회
        recent_commits = []
        try:
            log_res = subprocess.run(
                ["git", "log", "-n", "8", "--pretty=format:%h|%an|%cr|%s"],
                cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if log_res.returncode == 0 and log_res.stdout.strip():
                for line in log_res.stdout.strip().splitlines():
                    parts = line.split("|", 3)
                    if len(parts) == 4:
                        recent_commits.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3]
                        })
        except Exception:
            pass
        status_copy["recent_commits"] = recent_commits
        return status_copy

def sync_now():
    """수동 즉시 동기화 실행"""
    global _git_thread
    sync_db_to_json("수동 즉시 동기화")
    # 워커 스레드가 돌고 있으면 대기
    if _git_thread and _git_thread.is_alive():
        _git_thread.join(timeout=6.0)
    else:
        time.sleep(2.5)
        if _git_thread and _git_thread.is_alive():
            _git_thread.join(timeout=6.0)
    return get_git_sync_status()
