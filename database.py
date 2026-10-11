"""
온프라미스 SQLite 데이터베이스 관리 모듈
환자 관리, 방문 상담 일지, 약사 임상 메모, 커스텀 상호작용 규칙 관리
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "pharmacy.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 환자 마스터 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chart_no TEXT UNIQUE,
        name TEXT NOT NULL,
        birth_year TEXT,
        gender TEXT,
        phone TEXT,
        chronic_conditions TEXT,
        allergies TEXT,
        regular_meds TEXT,
        special_notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. 환자 방문 및 처방 복약지도 상담 기록 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        visit_date TEXT NOT NULL,
        hospital_name TEXT,
        hospital_dept TEXT,
        prescribed_drugs TEXT,
        ddi_risk_summary TEXT,
        counseling_notes TEXT,
        pharmacist_name TEXT DEFAULT '담당약사',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    )
    """)

    # 3. 약사 임상 지식 및 특정 병원/약물 메모 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pharmacist_memos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        target_drugs TEXT,
        hospital_dept TEXT,
        content TEXT NOT NULL,
        author_name TEXT DEFAULT '대표약사',
        tags TEXT,
        is_pinned INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. 약사 임상 메모 코멘트(댓글) 테이블 (다중 약사/파트타임 약사 협업)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memo_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memo_id INTEGER NOT NULL,
        author_name TEXT NOT NULL,
        comment_text TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (memo_id) REFERENCES pharmacist_memos(id) ON DELETE CASCADE
    )
    """)

    # 기존 DB에 신규 컬럼 안전 추가 (마이그레이션)
    try:
        cursor.execute("ALTER TABLE pharmacist_memos ADD COLUMN author_name TEXT DEFAULT '대표약사'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE patient_visits ADD COLUMN prescription_image TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE patient_visits ADD COLUMN ocr_raw_text TEXT")
    except sqlite3.OperationalError:
        pass

    # 기본 샘플 환자 데이터 및 임상 메모 삽입 (데이터가 없을 때만)
    cursor.execute("SELECT COUNT(*) FROM patients")
    if cursor.fetchone()[0] == 0:
        seed_sample_data(cursor)

    # 샘플 코멘트가 없을 경우 기본 코멘트 추가
    cursor.execute("SELECT COUNT(*) FROM memo_comments")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO memo_comments (memo_id, author_name, comment_text, created_at)
        VALUES 
        (1, '박약사 (오후파트)', '어제 3층 정형외과 원장님과 통화했습니다. 고령 환자 고혈압 약 확인 후 록소프로펜 대신 아세트아미노펜 복합제로 원내 오더 우선 고려하시겠다고 합니다.', datetime('now', '-2 hours')),
        (2, '최약사 (주말파트)', '클로피도그렐 복용 환자분들 위장약 처방 시 파모티딘 20mg 대체율이 높아지고 있습니다. 복약지도 시 확인 필수!', datetime('now', '-1 day'))
        """)

    conn.commit()
    conn.close()

def seed_sample_data(cursor):
    sample_patients = [
        (
            "P-2026-001", "김정훈", "1954", "남", "010-3849-1122",
            "고혈압, 심방세동(AFib), 당뇨", "페니실린 발진 병력",
            json.dumps(["리바록사반 (자렐토 20mg)", "로사르탄 50mg", "메트포르민 500mg"], ensure_ascii=False),
            "관절염 통증으로 정형외과 자주 방문함. 소염진통제(NSAID) 처방 시 출혈/신부전 위험 각별 모니터링 필요!"
        ),
        (
            "P-2026-002", "이지은", "1988", "여", "010-9921-4321",
            "주요우울장애(MDD), 편두통", "없음",
            json.dumps(["에스시탈로프람 (렉사프로 10mg)"], ensure_ascii=False),
            "감기나 두통약 구입 시 울트라셋(트라마돌) 및 마약성 진통제 병용 금기. 세로토닌 증후군 주의."
        ),
        (
            "P-2026-003", "박영수", "1960", "남", "010-5544-7788",
            "협심증 (스텐트 삽입술 기왕력), 고지혈증", "없음",
            json.dumps(["아스피린프로텍트 100mg", "클로피도그렐 75mg", "아토르바스타틴 20mg"], ensure_ascii=False),
            "위장장애 호소 시 오메프라졸 피하고 판토프라졸 또는 H2차단제 안내할 것. 이비인후과 항생제(클라리시드) 병용 금기."
        )
    ]
    cursor.executemany("""
    INSERT INTO patients (chart_no, name, birth_year, gender, phone, chronic_conditions, allergies, regular_meds, special_notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_patients)

    # 샘플 상담 이력
    sample_visits = [
        (
            1, "2026-10-08", "서울바른정형외과", "정형외과",
            "록소프로펜 60mg, 에페리손 50mg",
            "리바록사반+록소프로펜 중대 위험 (출혈 및 신손상 위험)",
            "정형외과 처방전에 록소프로펜이 포함되어 환자 복용 중인 자렐토(DOAC)와의 위장관 대출혈 위험 안내. 원장님 통화 후 아세트아미노펜 650mg ER로 대체 변경 조제함. 환자에게 멍이나 출혈 모니터링 교육."
        ),
        (
            2, "2026-09-25", "연세이비인후과", "이비인후과",
            "페니라민, 코싹엘, 타이레놀",
            "SSRI 복용 중 1세대 항히스타민 졸음 상승 주의",
            "기존 렉사프로 복용 중이므로 운전 시 졸음 주의 설명. 코막힘 심할 경우 비강 분무제 권유."
        )
    ]
    cursor.executemany("""
    INSERT INTO patient_visits (patient_id, visit_date, hospital_name, hospital_dept, prescribed_drugs, ddi_risk_summary, counseling_notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sample_visits)

    # 약사 실전 임상 지식 메모
    sample_memos = [
        (
            "3층 정형외과 ↔ 2층 내과 교차 처방 복약지도 팁",
            "병원입지별 주의",
            "이부프로펜, 록소프로펜, 로사르탄, 라미프릴, 푸로세미드",
            "정형외과, 내과",
            "우리 건물 2층 내과에서 ACEi/ARB+이뇨제 처방받는 어르신들이 3층 정형외과에서 무릎 통증으로 NSAID 받아가실 때 'Triple Whammy' 신부전 사례가 지난달 1건 관찰됨. 반드시 두 병원 처방 함께 확인하고 아세트아미노펜으로 우회 유도할 것.",
            "신부전,TripleWhammy,정형외과,내과",
            1
        ),
        (
            "오메프라졸과 클로피도그렐(플라빅스) 상호작용 대체 가이드",
            "DDI 임상 가이드",
            "클로피도그렐, 오메프라졸",
            "소화기내과, 순환기내과",
            "CYP2C19 저해로 플라빅스 활성 억제됨. PPI 필요 시 반드시 판토프라졸(판토록 등)이나 라베프라졸(파리에트 등)로 처방 변경 요청하거나 파모티딘으로 대체 권고.",
            "스텐트,혈전,플라빅스,CYP2C19",
            1
        ),
        (
            "4층 피부과 이소티논 환자 테트라사이클린계 병용 금기 확인 프로토콜",
            "병원입지별 주의",
            "독시사이클린, 미노사이클린, 이소트레티노인",
            "피부과",
            "여드름 치료 환자 중 간혹 타 병원에서 미노씬이나 독시사이클린 처방받고 여기서 이소티논 받아가는 경우 있음. 가뇌종양(뇌압상승) 및 영구 실명 위험 절대 금기! 조제 시 구두로 최근 복용 약물 필터링 필수.",
            "피부과,가뇌종양,두개내압",
            1
        )
    ]
    cursor.executemany("""
    INSERT INTO pharmacist_memos (title, category, target_drugs, hospital_dept, content, tags, is_pinned)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sample_memos)

