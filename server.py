"""
온프라미스 약학 약물 교차 및 상호 반응 전문가 웹 서비스 서버
(On-Premise Pharmacological DDI & Clinic Proximity Suite)
파이썬 표준 라이브러리 기반 무설치 단독 실행 웹서버
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import mimetypes
from datetime import datetime

import database
import ddi_data
import data_store
import socket

PORT = int(os.environ.get("PORT", 8085))
HOST = os.environ.get("HOST", "0.0.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_local_ip():
    """로컬 Wi-Fi 또는 이더넷 IPv4 주소 자동 감지"""
    ext_host = os.environ.get("EXTERNAL_HOST")
    if ext_host:
        return ext_host
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        if s:
            s.close()


class PharmacyRequestHandler(http.server.BaseHTTPRequestHandler):

    def end_headers(self):
        # CORS 및 캐시 제어
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def _send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(json_str.encode('utf-8'))

    def _send_error(self, message, status_code=400):
        self._send_json({"error": message, "status": status_code}, status_code=status_code)

    def _parse_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body_bytes = self.rfile.read(content_length)
            try:
                return json.loads(body_bytes.decode('utf-8'))
            except Exception:
                return {}
        return {}

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

    # ================= HTTP METHOD 라우터 =================
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path.startswith("/api/"):
            try:
                self._handle_api_get(path, query_params)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    self._send_error(f"서버 오류: {str(e)}", 500)
                except Exception:
                    pass
            return

        # 정적 파일 서빙 (HTML, CSS, JS)
        try:
            self._serve_static(path)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/api/"):
            try:
                body = self._parse_body()
                self._handle_api_post(path, body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                try:
                    self._send_error(f"서버 오류: {str(e)}", 500)
                except Exception:
                    pass
            return

        self._send_error("지원하지 않는 요청입니다.", 404)

    def do_PUT(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/api/"):
            try:
                body = self._parse_body()
                self._handle_api_put(path, body)
            except Exception as e:
                self._send_error(f"서버 오류: {str(e)}", 500)
            return

        self._send_error("지원하지 않는 요청입니다.", 404)

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/api/"):
            try:
                self._handle_api_delete(path)
            except Exception as e:
                self._send_error(f"서버 오류: {str(e)}", 500)
            return

        self._send_error("지원하지 않는 요청입니다.", 404)

    # ================= API GET 처리 =================
    def _handle_api_get(self, path, query_params):
        conn = database.get_db_connection()
        cursor = conn.cursor()

        try:
            # 네트워크 Wi-Fi 접속 정보
            if path == "/api/network-info":
                local_ip = get_local_ip()
                self._send_json({
                    "port": PORT,
                    "local_ip": local_ip,
                    "local_url": f"http://localhost:{PORT}",
                    "wifi_url": f"http://{local_ip}:{PORT}"
                })

            # Git 저장소 실시간 동기화 상태 조회
            elif path == "/api/git-sync-status":
                self._send_json(data_store.get_git_sync_status())

            # 시스템 종합 통계 (오른쪽 상단 DB 현황 표기)
            elif path == "/api/stats":
                cursor.execute("SELECT COUNT(*) FROM patients")
                patient_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM patient_visits")
                visit_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM pharmacist_memos")
                memo_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM memo_comments")
                comment_count = cursor.fetchone()[0]

                contraindicated_count = sum(1 for r in ddi_data.DDI_RULES if r.get("severity") == "CONTRAINDICATED")
                major_count = sum(1 for r in ddi_data.DDI_RULES if r.get("severity") == "MAJOR")

                self._send_json({
                    "total_drugs": len(ddi_data.DRUGS),
                    "total_rules": len(ddi_data.DDI_RULES),
                    "contraindicated_rules": contraindicated_count,
                    "major_rules": major_count,
                    "hospital_scenarios": len(ddi_data.HOSPITAL_LOCATION_GUIDES),
                    "sci_alerts_count": len(getattr(ddi_data, "RECENT_SCI_ALERTS", [])),
                    "patient_count": patient_count,
                    "visit_count": visit_count,
                    "memo_count": memo_count,
                    "comment_count": comment_count
                })

            # 최신 기록지 감지 API (우측 플로팅 아이콘용)
            elif path == "/api/latest-activity":
                cursor.execute("""
                    SELECT v.id, v.patient_id, v.visit_date, v.hospital_name, v.hospital_dept,
                           v.prescribed_drugs, v.counseling_notes, v.pharmacist_name, v.created_at,
                           p.name as patient_name, p.chart_no
                    FROM patient_visits v
                    JOIN patients p ON v.patient_id = p.id
                    ORDER BY v.id DESC LIMIT 1
                """)
                latest_visit = cursor.fetchone()

                cursor.execute("""
                    SELECT m.id, m.title, m.category, m.author_name, m.created_at, m.updated_at
                    FROM pharmacist_memos m
                    ORDER BY m.id DESC LIMIT 1
                """)
                latest_memo = cursor.fetchone()

                activity = None
                if latest_visit and latest_memo:
                    visit_time = latest_visit["created_at"]
                    memo_time = latest_memo["created_at"]
                    if visit_time >= memo_time:
                        activity = {
                            "type": "visit",
                            "id": latest_visit["id"],
                            "patient_id": latest_visit["patient_id"],
                            "title": f"{latest_visit['patient_name']} 환자 상담일지",
                            "subtitle": f"{latest_visit['hospital_name'] or '병원미상'} ({latest_visit['hospital_dept'] or '일반'})",
                            "author": latest_visit["pharmacist_name"],
                            "created_at": latest_visit["created_at"]
                        }
                    else:
                        activity = {
                            "type": "memo",
                            "id": latest_memo["id"],
                            "title": latest_memo["title"],
                            "subtitle": f"카테고리: {latest_memo['category']}",
                            "author": latest_memo["author_name"],
                            "created_at": latest_memo["created_at"]
                        }
                elif latest_visit:
                    activity = {
                        "type": "visit",
                        "id": latest_visit["id"],
                        "patient_id": latest_visit["patient_id"],
                        "title": f"{latest_visit['patient_name']} 환자 상담일지",
                        "subtitle": f"{latest_visit['hospital_name'] or '병원미상'}",
                        "author": latest_visit["pharmacist_name"],
                        "created_at": latest_visit["created_at"]
                    }
                elif latest_memo:
                    activity = {
                        "type": "memo",
                        "id": latest_memo["id"],
                        "title": latest_memo["title"],
                        "subtitle": f"카테고리: {latest_memo['category']}",
                        "author": latest_memo["author_name"],
                        "created_at": latest_memo["created_at"]
                    }

                self._send_json({"latest_activity": activity})

            # 약물 마스터 목록
            elif path == "/api/drugs":
                q = query_params.get("q", [""])[0].strip().lower()
                category = query_params.get("category", [""])[0]

                filtered = ddi_data.DRUGS
                if category:
                    filtered = [d for d in filtered if d["category"] == category]
                if q:
                    filtered = [
                        d for d in filtered
                        if q in d["name_ko"].lower()
                        or q in d["name_en"].lower()
                        or any(q in b.lower() for b in d["brand_names"])
                    ]

                self._send_json({
                    "categories": ddi_data.DRUG_CATEGORIES,
                    "drugs": filtered
                })

            # 최근 2개년 SCI 논문 위험 경보 목록 (상단 공지사항용)
            elif path == "/api/sci-alerts":
                self._send_json({
                    "alerts": getattr(ddi_data, "RECENT_SCI_ALERTS", [])
                })

            # 상호작용 규칙 전체 목록
            elif path == "/api/rules":
                self._send_json({
                    "rules": ddi_data.DDI_RULES
                })

            # 병원 입지별 가이드 목록
            elif path == "/api/hospital-guides":
                self._send_json({
                    "guides": ddi_data.HOSPITAL_LOCATION_GUIDES
                })

            # 특정 환자 목록
            elif path == "/api/patients":
                q = query_params.get("q", [""])[0].strip()
                if q:
                    cursor.execute("""
                        SELECT * FROM patients
                        WHERE name LIKE ? OR chart_no LIKE ? OR phone LIKE ? OR chronic_conditions LIKE ?
                        ORDER BY updated_at DESC
                    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
                else:
                    cursor.execute("SELECT * FROM patients ORDER BY updated_at DESC")

                rows = [dict(r) for r in cursor.fetchall()]
                for r in rows:
                    try:
                        r["regular_meds"] = json.loads(r["regular_meds"]) if r["regular_meds"] else []
                    except:
                        r["regular_meds"] = []

                self._send_json({"patients": rows})

            # 환자 상세 및 방문 이력
            elif path.startswith("/api/patients/"):
                patient_id = int(path.split("/")[-1])
                cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
                patient_row = cursor.fetchone()
                if not patient_row:
                    self._send_error("환자를 찾을 수 없습니다.", 404)
                    return

                patient = dict(patient_row)
                try:
                    patient["regular_meds"] = json.loads(patient["regular_meds"]) if patient["regular_meds"] else []
                except:
                    patient["regular_meds"] = []

                cursor.execute("""
                    SELECT * FROM patient_visits
                    WHERE patient_id = ?
                    ORDER BY visit_date DESC, id DESC
                """, (patient_id,))
                visits = [dict(v) for v in cursor.fetchall()]

                self._send_json({
                    "patient": patient,
                    "visits": visits
                })

            # 약사 메모 목록 (각 메모의 코멘트 포함)
            elif path == "/api/memos":
                q = query_params.get("q", [""])[0].strip()
                category = query_params.get("category", [""])[0]

                sql = "SELECT * FROM pharmacist_memos WHERE 1=1"
                params = []

                if category:
                    sql += " AND category = ?"
                    params.append(category)

                if q:
                    sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ? OR target_drugs LIKE ? OR author_name LIKE ?)"
                    params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])

                sql += " ORDER BY is_pinned DESC, updated_at DESC"
                cursor.execute(sql, params)
                memos = [dict(m) for m in cursor.fetchall()]

                # 각 메모별 코멘트(댓글) 가져오기
                for memo in memos:
                    cursor.execute("""
                        SELECT * FROM memo_comments
                        WHERE memo_id = ?
                        ORDER BY created_at ASC
                    """, (memo["id"],))
                    memo["comments"] = [dict(c) for c in cursor.fetchall()]

                self._send_json({"memos": memos})

            else:
                self._send_error("요청한 API가 존재하지 않습니다.", 404)

        finally:
            conn.close()

    # ================= API POST 처리 =================
    def _handle_api_post(self, path, body):
        conn = database.get_db_connection()
        cursor = conn.cursor()

        try:
            # 0-1. Git 즉시 수동 동기화
            if path == "/api/git-sync-now":
                status = data_store.sync_now()
                response_data = dict(status)
                response_data["success"] = True
                response_data["commit_hash"] = status.get("commit_hash") or status.get("last_commit_hash")
                self._send_json(response_data)
                return

            # 0-2. 신규 의약품 등록 (한국형 DDInter 지속 축적 엔진)
            elif path == "/api/drugs":
                try:
                    res = data_store.add_new_drug(body)
                    res["success"] = True
                    self._send_json(res, 201)
                except Exception as e:
                    self._send_error(str(e), 400)
                return

            # 0-3. 신규 DDI 상호작용 규칙 등록 (한국형 DDInter 지속 축적 엔진)
            elif path == "/api/rules":
                try:
                    res = data_store.add_new_rule(body)
                    res["success"] = True
                    self._send_json(res, 201)
                except Exception as e:
                    self._send_error(str(e), 400)
                return

            # 1. 약물 상호작용 분석 엔진 (DDI Checker)
            elif path == "/api/check-ddi":
                selected_drug_ids = body.get("drug_ids", [])
                if not selected_drug_ids or len(selected_drug_ids) < 2:
                    self._send_json({
                        "selected_drugs": [],
                        "interactions_found": 0,
                        "contraindicated_count": 0,
                        "major_count": 0,
                        "moderate_count": 0,
                        "results": [],
                        "message": "상호작용 검사를 위해 2개 이상의 약물을 선택해주세요."
                    })
                    return

                selected_drugs_info = [d for d in ddi_data.DRUGS if d["id"] in selected_drug_ids]
                results = []

                for rule in ddi_data.DDI_RULES:
                    rule_drugs = rule["drugs"]
                    if all(rd in selected_drug_ids for rd in rule_drugs):
                        drug_a_info = next((d for d in ddi_data.DRUGS if d["id"] == rule_drugs[0]), None)
                        drug_b_info = next((d for d in ddi_data.DRUGS if d["id"] == rule_drugs[1]), None)

                        results.append({
                            "rule_id": rule["id"],
                            "severity": rule["severity"],
                            "severity_ko": rule["severity_ko"],
                            "title": rule["title"],
                            "is_recent_sci": rule.get("is_recent_sci", False),
                            "sci_journal": rule.get("sci_journal", ""),
                            "sci_year": rule.get("sci_year", ""),
                            "sci_badge": rule.get("sci_badge", "최신 정보 (최근 2개년 SCI)"),
                            "drug_a": drug_a_info,
                            "drug_b": drug_b_info,
                            "mechanism": rule["mechanism"],
                            "adverse_reactions": rule["adverse_reactions"],
                            "clinical_action": rule["clinical_action"],
                            "hospital_department": rule.get("hospital_department", "")
                        })

                # 심각도별 정렬: CONTRAINDICATED -> MAJOR -> MODERATE
                severity_order = {"CONTRAINDICATED": 0, "MAJOR": 1, "MODERATE": 2}
                results.sort(key=lambda x: severity_order.get(x["severity"], 9))

                contraindicated_count = sum(1 for r in results if r["severity"] == "CONTRAINDICATED")
                major_count = sum(1 for r in results if r["severity"] == "MAJOR")
                moderate_count = sum(1 for r in results if r["severity"] == "MODERATE")

                self._send_json({
                    "selected_drugs": selected_drugs_info,
                    "interactions_found": len(results),
                    "contraindicated_count": contraindicated_count,
                    "major_count": major_count,
                    "moderate_count": moderate_count,
                    "results": results
                })

            # 2. 약봉투 OCR 텍스트 기반 DB 약물 자동 매칭 엔진
            elif path == "/api/match-drugs-from-text":
                raw_text = body.get("text", "")
                lower_text = raw_text.lower()

                matched = []
                matched_drug_ids = set()

                for d in ddi_data.DRUGS:
                    hit = False
                    matched_kw = ""

                    # 한글 성분명 검사
                    if d["name_ko"] in raw_text:
                        hit = True
                        matched_kw = d["name_ko"]
                    # 영문명 검사
                    elif d["name_en"].lower() in lower_text:
                        hit = True
                        matched_kw = d["name_en"]
                    else:
                        # 브랜드/상품명 검사
                        for brand in d.get("brand_names", []):
                            clean_brand = brand.split("(")[0].strip()
                            if clean_brand and clean_brand in raw_text:
                                hit = True
                                matched_kw = clean_brand
                                break

                    if hit and d["id"] not in matched_drug_ids:
                        matched_drug_ids.add(d["id"])
                        matched.append({
                            "drug": d,
                            "matched_keyword": matched_kw
                        })

                self._send_json({
                    "raw_text": raw_text,
                    "matched_count": len(matched),
                    "matched_drugs": matched
                })

            # 3. 신규 환자 등록
            elif path == "/api/patients":
                name = body.get("name", "").strip()
                if not name:
                    self._send_error("환자 이름은 필수입니다.", 400)
                    return

                chart_no = body.get("chart_no", "").strip()
                if not chart_no:
                    chart_no = f"P-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                regular_meds = json.dumps(body.get("regular_meds", []), ensure_ascii=False)

                cursor.execute("""
                    INSERT INTO patients (chart_no, name, birth_year, gender, phone, chronic_conditions, allergies, regular_meds, special_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chart_no,
                    name,
                    body.get("birth_year", ""),
                    body.get("gender", "기타"),
                    body.get("phone", ""),
                    body.get("chronic_conditions", ""),
                    body.get("allergies", ""),
                    regular_meds,
                    body.get("special_notes", "")
                ))
                new_id = cursor.lastrowid
                conn.commit()
                data_store.sync_db_to_json(f"신규 환자 등록: {name}")
                self._send_json({
                    "id": new_id,
                    "chart_no": chart_no,
                    "message": "환자가 등록되었습니다."
                }, 201)

            # 4. 환자 방문 및 복약지도 상담 기록 추가 (약봉투 사진 및 OCR 텍스트 포함)
            elif path.startswith("/api/patients/") and path.endswith("/visits"):
                parts = path.split("/")
                patient_id = int(parts[3])

                cursor.execute("""
                    INSERT INTO patient_visits (patient_id, visit_date, hospital_name, hospital_dept, prescribed_drugs, ddi_risk_summary, counseling_notes, pharmacist_name, prescription_image, ocr_raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id,
                    body.get("visit_date", datetime.now().strftime("%Y-%m-%d")),
                    body.get("hospital_name", ""),
                    body.get("hospital_dept", ""),
                    body.get("prescribed_drugs", ""),
                    body.get("ddi_risk_summary", ""),
                    body.get("counseling_notes", ""),
                    body.get("pharmacist_name", "담당약사"),
                    body.get("prescription_image", ""),
                    body.get("ocr_raw_text", "")
                ))
                new_visit_id = cursor.lastrowid

                # 환자 updated_at 갱신
                cursor.execute("UPDATE patients SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (patient_id,))
                conn.commit()
                data_store.sync_db_to_json(f"환자 방문 상담일지 등록: 환자 ID {patient_id}")
                self._send_json({
                    "visit_id": new_visit_id,
                    "message": "방문 및 상담 기록(새 기록지)이 성공적으로 등록되었습니다."
                })

            # 5. 약사 임상 메모 등록 (작성 약사명 포함)
            elif path == "/api/memos":
                title = body.get("title", "").strip()
                content = body.get("content", "").strip()
                if not title or not content:
                    self._send_error("제목과 내용은 필수입니다.", 400)
                    return

                author_name = body.get("author_name", "대표약사").strip() or "대표약사"

                cursor.execute("""
                    INSERT INTO pharmacist_memos (title, category, target_drugs, hospital_dept, content, author_name, tags, is_pinned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    body.get("category", "임상 노트"),
                    body.get("target_drugs", ""),
                    body.get("hospital_dept", ""),
                    content,
                    author_name,
                    body.get("tags", ""),
                    1 if body.get("is_pinned") else 0
                ))
                new_memo_id = cursor.lastrowid
                conn.commit()
                data_store.sync_db_to_json(f"약사 임상 메모 등록: {title}")
                self._send_json({
                    "id": new_memo_id,
                    "message": "약사 임상 메모(새 기록지)가 성공적으로 등록되었습니다."
                })

            # 6. 약사 메모에 다른 약사의 코멘트/의견 등록 (다중 약사/파트타임 협업)
            elif path.startswith("/api/memos/") and path.endswith("/comments"):
                parts = path.split("/")
                memo_id = int(parts[3])

                author_name = body.get("author_name", "파트약사").strip() or "파트약사"
                comment_text = body.get("comment_text", "").strip()

                if not comment_text:
                    self._send_error("코멘트 내용은 필수입니다.", 400)
                    return

                cursor.execute("""
                    INSERT INTO memo_comments (memo_id, author_name, comment_text)
                    VALUES (?, ?, ?)
                """, (memo_id, author_name, comment_text))
                new_comment_id = cursor.lastrowid

                # 메모의 updated_at 갱신
                cursor.execute("UPDATE pharmacist_memos SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (memo_id,))
                conn.commit()
                data_store.sync_db_to_json(f"약사 코멘트 등록: 메모 ID {memo_id}")
                self._send_json({
                    "id": new_comment_id,
                    "message": "약사 코멘트가 성공적으로 등록되었습니다."
                })

            else:
                self._send_error("지원하지 않는 API입니다.", 404)

        finally:
            conn.close()

    # ================= API PUT 처리 =================
    def _handle_api_put(self, path, body):
        conn = database.get_db_connection()
        cursor = conn.cursor()

        try:
            # 환자 정보 수정
            if path.startswith("/api/patients/"):
                patient_id = int(path.split("/")[-1])
                regular_meds = json.dumps(body.get("regular_meds", []), ensure_ascii=False)

                cursor.execute("""
                    UPDATE patients
                    SET name = ?, birth_year = ?, gender = ?, phone = ?, chronic_conditions = ?,
                        allergies = ?, regular_meds = ?, special_notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    body.get("name", ""),
                    body.get("birth_year", ""),
                    body.get("gender", ""),
                    body.get("phone", ""),
                    body.get("chronic_conditions", ""),
                    body.get("allergies", ""),
                    regular_meds,
                    body.get("special_notes", ""),
                    patient_id
                ))
                conn.commit()
                data_store.sync_db_to_json(f"환자 정보 수정: ID {patient_id}")
                self._send_json({"message": "환자 정보가 수정되었습니다."})

            # 약사 메모 수정
            elif path.startswith("/api/memos/"):
                memo_id = int(path.split("/")[-1])
                cursor.execute("""
                    UPDATE pharmacist_memos
                    SET title = ?, category = ?, target_drugs = ?, hospital_dept = ?,
                        content = ?, author_name = ?, tags = ?, is_pinned = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    body.get("title", ""),
                    body.get("category", "임상 노트"),
                    body.get("target_drugs", ""),
                    body.get("hospital_dept", ""),
                    body.get("content", ""),
                    body.get("author_name", "대표약사"),
                    body.get("tags", ""),
                    1 if body.get("is_pinned") else 0,
                    memo_id
                ))
                conn.commit()
                data_store.sync_db_to_json(f"약사 임상 메모 수정: ID {memo_id}")
                self._send_json({"message": "메모가 수정되었습니다."})

            else:
                self._send_error("지원하지 않는 API입니다.", 404)

        finally:
            conn.close()

    # ================= API DELETE 처리 =================
    def _handle_api_delete(self, path):
        conn = database.get_db_connection()
        cursor = conn.cursor()

        try:
            # 코멘트 삭제
            if path.startswith("/api/comments/"):
                comment_id = int(path.split("/")[-1])
                cursor.execute("DELETE FROM memo_comments WHERE id = ?", (comment_id,))
                conn.commit()
                data_store.sync_db_to_json(f"약사 코멘트 삭제: ID {comment_id}")
                self._send_json({"message": "코멘트가 삭제되었습니다."})

            # 환자 삭제
            elif path.startswith("/api/patients/"):
                patient_id = int(path.split("/")[-1])
                cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
                cursor.execute("DELETE FROM patient_visits WHERE patient_id = ?", (patient_id,))
                conn.commit()
                data_store.sync_db_to_json(f"환자 정보 삭제: ID {patient_id}")
                self._send_json({"message": "환자 정보가 삭제되었습니다."})

            # 약사 메모 삭제
            elif path.startswith("/api/memos/"):
                memo_id = int(path.split("/")[-1])
                cursor.execute("DELETE FROM pharmacist_memos WHERE id = ?", (memo_id,))
                cursor.execute("DELETE FROM memo_comments WHERE memo_id = ?", (memo_id,))
                conn.commit()
                data_store.sync_db_to_json(f"약사 임상 메모 삭제: ID {memo_id}")
                self._send_json({"message": "메모가 삭제되었습니다."})

            else:
                self._send_error("지원하지 않는 API입니다.", 404)

        finally:
            conn.close()

    # ================= 정적 파일 서빙 =================
    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"

        # 보안 검사 (상위 디렉토리 이동 방지)
        clean_path = os.path.normpath(path.lstrip("/"))
        file_path = os.path.join(STATIC_DIR, clean_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(STATIC_DIR, "index.html")

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "text/plain"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Static file error: {str(e)}".encode('utf-8'))

def run_server():
    database.init_db()
    data_store.init_data_store()
    with http.server.ThreadingHTTPServer((HOST, PORT), PharmacyRequestHandler) as httpd:
        print("="*65)
        print(" [Pharm-DDI Expert Suite] 온프라미스 약학 전문가 시스템 가동")
        print(f" * 로컬 웹 서비스 URL: http://localhost:{PORT}")
        print(f" * 네트워크 접근 URL: http://127.0.0.1:{PORT}")
        print(" * 통계 배지, 2개년 SCI 경보, 3단계 입지가이드, 약봉투 OCR, 다중약사 메모")
        print("="*65)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버가 안전하게 종료되었습니다.")

if __name__ == "__main__":
    run_server()
