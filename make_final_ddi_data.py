# -*- coding: utf-8 -*-
"""
Construct final ddi_data.py preserving RECENT_SCI_ALERTS and HOSPITAL_LOCATION_GUIDES,
while importing 516+ DRUGS and 760+ DDI_RULES.
"""
import json
import ddi_data

sci_alerts = ddi_data.RECENT_SCI_ALERTS
guides = ddi_data.HOSPITAL_LOCATION_GUIDES

content = f'''# -*- coding: utf-8 -*-
"""
약학 약물 상호작용 및 병용금기/주의 지식 베이스 (516종 의약품 / 766건 DDI 규칙 대확장판)
(Korean Drug-Drug Interaction & Clinical Practice Knowledge Engine)
식약처 의약품안전사용서비스(DUR) 병용금기 및 글로벌 임상 DDI 기준 반영
"""

from builder_drugs import DRUG_CATEGORIES, DRUGS
from builder_rules import DDI_RULES

# 최근 2개년 (2024~2025) 약학 SCI 논문 신규 가설 및 임상 경보 (4건)
RECENT_SCI_ALERTS = {repr(sci_alerts)}

# 병원 입지별 복약지도 & 조제 검수 가이드 (3단계 계층: 고위험 / 경고 / 주의)
HOSPITAL_LOCATION_GUIDES = {repr(guides)}

print(f"Loaded master DDI data: {{len(DRUGS)}} drugs, {{len(DDI_RULES)}} rules, {{len(RECENT_SCI_ALERTS)}} SCI alerts, {{len(HOSPITAL_LOCATION_GUIDES)}} location guides.")
'''

with open("ddi_data.py", "w", encoding="utf-8") as f:
    f.write(content)

print("ddi_data.py has been successfully regenerated!")
