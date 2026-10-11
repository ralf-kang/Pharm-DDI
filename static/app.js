/**
 * Pharm-DDI Expert Suite - Mobile-Responsive Application Logic
 * 최신 2개년 SCI 경보, 3단계 입지 위험도, 약봉투 자체 OCR, 다중약사 코멘트, 우측 플로팅 신규기록지 배너
 */

// 전역 상태
const state = {
  drugs: [],
  categories: [],
  selectedDrugIds: new Set(),
  hospitalGuides: [],
  selectedGuideId: null,
  patients: [],
  selectedPatientId: null,
  memos: [],
  rules: [],
  sciAlerts: [],
  stats: {},
  latestActivity: null,
  currentBagImageBase64: null,
  ocrMatchedDrugs: [],
  networkInfo: {
    local_ip: '127.0.0.1',
    access_url: 'http://localhost:8085'
  },
  gitSync: {
    is_syncing: false,
    last_commit_hash: '4e0ed1a',
    status: 'synced',
    total_drugs: 516,
    total_rules: 766
  }
};

// ================= 초기화 =================
document.addEventListener('DOMContentLoaded', async () => {
  initSystemClock();
  setupNavigationTabs();
  setupEventListeners();
  setupOcrListeners();
  setupDdinterListeners();

  await loadNetworkInfo();
  await loadStats();
  await loadSciAlerts();
  await loadDrugs();
  await loadHospitalGuides();
  await loadPatients();
  await loadMemos();
  await loadRules();
  await checkLatestActivity();
  await loadGitSyncStatus();

  // 15초마다 최신 기록지 상태 백그라운드 갱신
  setInterval(checkLatestActivity, 15000);
  // 30초마다 Git 동기화 상태 갱신
  setInterval(loadGitSyncStatus, 30000);
});

// 시계 업데이트
function initSystemClock() {
  const clockEl = document.getElementById('systemClock');
  if (!clockEl) return;
  const update = () => {
    const now = new Date();
    clockEl.textContent = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  };
  update();
  setInterval(update, 30000);
}

// 탭 전환 (모바일 부드러운 스크롤 정렬 지원)
function setupNavigationTabs() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');

      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add('active');
      }

      // 모바일 환경에서 활성 탭 버튼이 화면 중앙으로 스크롤되도록 보정
      btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });

      // 탭 전환 시 필요한 데이터 리프레시
      if (targetId === 'tab-patients') loadPatients();
      if (targetId === 'tab-memos') loadMemos();
      if (targetId === 'tab-ddinter') renderDdinterView();
    });
  });
}

// ================= 시스템 통계 및 우측 상단 데이터베이스 규모 로드 =================
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();
    state.stats = data;

    // 1. 우측 상단 헤더 데이터베이스 수집 규모 배지 갱신
    const hDrugs = document.getElementById('hStatDrugs');
    const hRules = document.getElementById('hStatRules');
    const hGuides = document.getElementById('hStatGuides');
    if (hDrugs) hDrugs.textContent = data.total_drugs || 516;
    if (hRules) hRules.textContent = data.total_rules || 766;
    if (hGuides) hGuides.textContent = data.hospital_scenarios || 5;

    // 2. 상단 메트릭 카드 갱신
    const elDrugs = document.getElementById('metricDrugs');
    const elRules = document.getElementById('metricRules');
    const elScenarios = document.getElementById('metricScenarios');
    const elPatients = document.getElementById('metricPatients');
    const elMemos = document.getElementById('metricMemos');

    if (elDrugs) elDrugs.textContent = `${data.total_drugs}종`;
    if (elRules) elRules.textContent = `${data.total_rules}건`;
    if (elScenarios) elScenarios.textContent = `${data.hospital_scenarios}개과`;
    if (elPatients) elPatients.textContent = `${data.patient_count}명`;
    if (elMemos) elMemos.textContent = `${data.memo_count}건`;

    const libD = document.getElementById('libDrugCount');
    const libR = document.getElementById('libRuleCount');
    if (libD) libD.textContent = data.total_drugs;
    if (libR) libR.textContent = data.total_rules;
  } catch (err) {
    console.error('Failed to load stats', err);
  }
}

// ================= 최신 기록지 감지 및 우측 플로팅 아이콘 유지 =================
async function checkLatestActivity() {
  try {
    const res = await fetch('/api/latest-activity');
    if (!res.ok) return;
    const data = await res.json();
    const act = data.latest_activity;
    state.latestActivity = act;

    const badge = document.getElementById('floatingNewRecordBadge');
    if (!badge) return;

    if (!act) {
      badge.style.display = 'none';
      return;
    }

    // 새로운 기록지가 나오기 전까지 우측에 고정 유지
    badge.style.display = 'flex';

    const titleEl = document.getElementById('floatingBadgeTitle');
    const subEl = document.getElementById('floatingBadgeSub');

    if (act.type === 'visit') {
      if (titleEl) titleEl.textContent = `📋 [새 상담일지] ${act.title}`;
      if (subEl) subEl.textContent = `${act.subtitle} • ${act.author} 약사 (${act.created_at ? act.created_at.substring(5, 16) : '최근'})`;
    } else {
      if (titleEl) titleEl.textContent = `📝 [새 임상메모] ${act.title}`;
      if (subEl) subEl.textContent = `${act.subtitle} • ${act.author} 약사 (${act.created_at ? act.created_at.substring(5, 16) : '최근'})`;
    }

    // 플로팅 뱃지 클릭 시 해당 기록지로 바로 이동
    const contentEl = document.getElementById('floatingBadgeContent');
    if (contentEl) {
      contentEl.onclick = () => {
        if (act.type === 'visit') {
          const tabBtn = document.querySelector('[data-tab="tab-patients"]');
          if (tabBtn) tabBtn.click();
          if (act.patient_id) {
            selectPatient(act.patient_id);
          }
        } else {
          const tabBtn = document.querySelector('[data-tab="tab-memos"]');
          if (tabBtn) tabBtn.click();
          loadMemos();
          const memoCard = document.querySelector(`.memo-card[data-id="${act.id}"]`);
          if (memoCard) {
            memoCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            memoCard.classList.add('highlight-pulse');
          }
        }
      };
    }

    const closeBtn = document.getElementById('btnCloseFloatingBadge');
    if (closeBtn) {
      closeBtn.onclick = (e) => {
        e.stopPropagation();
        badge.style.display = 'none';
      };
    }
  } catch (err) {
    console.error('Failed to check latest activity', err);
  }
}

// ================= 네트워크 Wi-Fi 접속 정보 로드 =================
async function loadNetworkInfo() {
  try {
    const res = await fetch('/api/network-info');
    if (!res.ok) return;
    const data = await res.json();
    state.networkInfo = data;

    const ipLabel = document.getElementById('ipDisplayLabel');
    if (ipLabel) {
      ipLabel.textContent = `Wi-Fi: ${data.local_ip}`;
    }

    const mobileInput = document.getElementById('mobileAccessUrlInput');
    if (mobileInput) {
      mobileInput.value = data.wifi_url || data.local_url;
    }

    renderQrCode(data.wifi_url || data.local_url);
  } catch (err) {
    console.error('Failed to load network info', err);
  }
}

// ================= 최근 2개년(2024~2026) SCI 논문 경보 로드 및 상단 공지 렌더링 =================
async function loadSciAlerts() {
  try {
    const res = await fetch('/api/sci-alerts');
    if (!res.ok) return;
    const data = await res.json();
    state.sciAlerts = data.alerts || [];

    const badge = document.getElementById('sciAlertCountBadge');
    if (badge) badge.textContent = `${state.sciAlerts.length}건`;

    renderSciNoticeBanner();
  } catch (err) {
    console.error('Failed to load SCI alerts', err);
  }
}

function renderSciNoticeBanner() {
  const container = document.getElementById('sciNoticeSlider');
  if (!container) return;

  if (state.sciAlerts.length === 0) {
    container.innerHTML = '<div style="padding:16px; color:#6b21a8; font-size:0.875rem;">등록된 최신 연구 경보가 없습니다.</div>';
    return;
  }

  container.innerHTML = state.sciAlerts.map(a => `
    <div class="sci-alert-card" data-id="${a.id}">
      <div>
        <div class="sci-alert-top">
          <span class="sci-journal-tag">📄 ${a.journal}</span>
          <span class="severity-pill pill-${a.severity}">${a.severity_ko}</span>
        </div>
        <div class="sci-alert-title" style="margin-top:8px;">${a.title}</div>
        <div class="sci-hypothesis-text" style="margin-top:8px;">
          <strong>🔬 2024 최신 규명 기전:</strong> ${a.hypothesis}
        </div>
      </div>
      <div class="sci-alert-footer">
        <span class="sci-drugs-tag">💊 대상: ${a.drugs.join(' + ')}</span>
        <button class="btn-test-sci" onclick="testSciAlert('${a.id}')">⚡ 검사기에 로드</button>
      </div>
    </div>
  `).join('');
}

// 상단 공지사항 카드에서 원클릭으로 검사기에 로드
window.testSciAlert = function(alertId) {
  const alert = state.sciAlerts.find(a => a.id === alertId);
  if (!alert) return;

  state.selectedDrugIds.clear();

  if (alertId === 'SCI-ALERT-2024-01') {
    state.selectedDrugIds.add('rivaroxaban');
    state.selectedDrugIds.add('escitalopram');
  } else if (alertId === 'SCI-ALERT-2024-02') {
    state.selectedDrugIds.add('allopurinol');
    state.selectedDrugIds.add('azathioprine');
  } else if (alertId === 'SCI-ALERT-2024-03') {
    state.selectedDrugIds.add('dapagliflozin');
    state.selectedDrugIds.add('furosemide');
  } else if (alertId === 'SCI-ALERT-2024-04') {
    state.selectedDrugIds.add('amlodipine');
    state.selectedDrugIds.add('simvastatin');
  }

  const ddiTabBtn = document.querySelector('[data-tab="tab-ddi"]');
  if (ddiTabBtn) ddiTabBtn.click();

  updateSelectedTagsBox();
  renderDrugList();
  runDdiCheck();

  showToast(`최신 SCI 경보 [${alert.journal}] 대상 약물이 검사기에 로드되었습니다.`, 'info');
};

// ================= 탭 1: 약물 및 DDI 검사기 =================
async function loadDrugs() {
  try {
    const res = await fetch('/api/drugs');
    const data = await res.json();
    state.drugs = data.drugs;
    state.categories = data.categories;

    const catSelect = document.getElementById('drugCategoryFilter');
    catSelect.innerHTML = '<option value="">모든 약효 분류 전체</option>';
    data.categories.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      catSelect.appendChild(opt);
    });

    renderDrugList();
    renderLibraryDrugs();
  } catch (err) {
    showToast('약물 목록을 불러오지 못했습니다.', 'error');
  }
}

function renderDrugList() {
  const container = document.getElementById('drugListContainer');
  const query = document.getElementById('drugSearchInput').value.trim().toLowerCase();
  const selectedCat = document.getElementById('drugCategoryFilter').value;

  const filtered = state.drugs.filter(d => {
    const matchesCat = !selectedCat || d.category === selectedCat;
    const matchesQuery = !query || 
      d.name_ko.toLowerCase().includes(query) ||
      d.name_en.toLowerCase().includes(query) ||
      d.brand_names.some(b => b.toLowerCase().includes(query)) ||
      (d.class && d.class.toLowerCase().includes(query));
    return matchesCat && matchesQuery;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding:24px; color:#94a3b8; font-size:0.875rem;">일치하는 약물이 없습니다.</div>';
    return;
  }

  container.innerHTML = filtered.map(drug => {
    const isSelected = state.selectedDrugIds.has(drug.id);
    return `
      <div class="drug-item-card ${isSelected ? 'selected' : ''}" data-id="${drug.id}">
        <div class="drug-main-info">
          <div class="drug-title-row">
            <span class="drug-name-ko">${drug.name_ko}</span>
          </div>
          <div class="drug-item-en">${drug.name_en} <span class="drug-class-tag">${drug.class ? `(${drug.class})` : ''}</span></div>
          <div class="drug-brands">대표제품: ${drug.brand_names ? drug.brand_names.join(', ') : '-'}</div>
        </div>
        <div class="drug-meta-right">
          <span class="drug-badge">${drug.category.split(' ')[0]}</span>
          <span class="drug-select-indicator ${isSelected ? 'is-selected' : ''}">
            ${isSelected ? '✓ 선택됨' : '+ 추가'}
          </span>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.drug-item-card').forEach(card => {
    card.addEventListener('click', () => {
      const drugId = card.getAttribute('data-id');
      toggleDrugSelection(drugId);
    });
  });
}

function toggleDrugSelection(drugId) {
  if (state.selectedDrugIds.has(drugId)) {
    state.selectedDrugIds.delete(drugId);
  } else {
    state.selectedDrugIds.add(drugId);
  }
  updateSelectedTagsBox();
  renderDrugList();
}

// 선택된 약물 태그 박스 (한글 텍스트 오버플로우 방지 및 태그 칩 처리)
function updateSelectedTagsBox() {
  const container = document.getElementById('selectedTagsBox');
  const countBadge = document.getElementById('selectedCountBadge');
  countBadge.textContent = `${state.selectedDrugIds.size}개 선택됨`;

  if (state.selectedDrugIds.size === 0) {
    container.innerHTML = '<div class="placeholder-text">아래 목록에서 검사할 약물을 터치하여 추가하세요. (최소 2개 이상)</div>';
    return;
  }

  const selectedDrugs = state.drugs.filter(d => state.selectedDrugIds.has(d.id));
  container.innerHTML = selectedDrugs.map(d => `
    <div class="drug-tag" title="${d.name_ko} (${d.name_en})">
      <span class="tag-name">${d.name_ko}</span>
      <span class="tag-remove" data-id="${d.id}">&times;</span>
    </div>
  `).join('');

  container.querySelectorAll('.tag-remove').forEach(rm => {
    rm.addEventListener('click', (e) => {
      e.stopPropagation();
      const drugId = rm.getAttribute('data-id');
      state.selectedDrugIds.delete(drugId);
      updateSelectedTagsBox();
      renderDrugList();
    });
  });
}

// 상호작용 검사 실행
async function runDdiCheck() {
  const ids = Array.from(state.selectedDrugIds);
  if (ids.length < 2) {
    showToast('상호작용 검사를 위해 2개 이상의 약물을 선택해주세요.', 'warning');
    return;
  }

  const container = document.getElementById('ddiResultContainer');
  container.innerHTML = '<div style="text-align:center; padding:48px; color:#0284c7;">⚡ 복합 약리학적 상호작용 및 최신 SCI 가설 분석 중...</div>';

  try {
    const res = await fetch('/api/check-ddi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drug_ids: ids })
    });
    const data = await res.json();

    const summaryBadges = document.getElementById('resultSummaryBadges');
    summaryBadges.innerHTML = `
      <span class="badge pill-CONTRAINDICATED">병용금기 ${data.contraindicated_count}건</span>
      <span class="badge pill-MAJOR">중대한 위험 ${data.major_count}건</span>
      <span class="badge pill-MODERATE">주의 ${data.moderate_count}건</span>
    `;

    if (data.interactions_found === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon" style="color:#059669;">✅</div>
          <h3 style="color:#059669;">선택된 약물 간 알려진 중대한 상호작용이 없습니다</h3>
          <p>선택하신 ${data.selected_drugs.length}가지 약물은 일반적인 용량 범위 내에서 병용 투여가 비교적 안전합니다.<br>
             (단, 개별 환자의 신기능·간기능 저하 및 고령 환자에서의 대사 지연 가능성은 별도 고려 바랍니다.)</p>
        </div>
      `;
      return;
    }

    container.innerHTML = data.results.map(r => `
      <div class="ddi-card severity-${r.severity}">
        <div class="ddi-card-header">
          <div class="ddi-title">
            ${r.is_recent_sci ? `<span class="pill-recent-sci" style="margin-right:6px;">🔬 ${r.sci_badge || '최신 정보 (최근 2개년 SCI)'}</span>` : ''}
            ⚠️ ${r.title}
          </div>
          <span class="severity-pill pill-${r.severity}">${r.severity_ko}</span>
        </div>

        ${r.is_recent_sci ? `
          <div class="sci-evidence-banner">
            <div class="sci-badge-label">
              <span>🔬 최근 2개년 권위 SCI 논문 근거</span>
              <span>• ${r.sci_year || '2024'}</span>
            </div>
            <div class="sci-journal-info">📄 논문 출처: <strong>${r.sci_journal}</strong></div>
          </div>
        ` : ''}

        <div class="hospital-dept-tag">🏥 관련 진료과 충돌: ${r.hospital_department || '일반 내과/가정의학과'}</div>

        <div class="ddi-section">
          <div class="ddi-section-label">${r.is_recent_sci ? '🔬 약리학적 기전 및 최신 연구 가설' : '약리학적 상호작용 기전'}</div>
          <div class="ddi-section-content">${r.mechanism}</div>
        </div>

        <div class="ddi-section">
          <div class="ddi-section-label">발생 가능한 부작용 및 임상 증상</div>
          <ul class="adverse-list">
            ${r.adverse_reactions.map(a => `<li>${a}</li>`).join('')}
          </ul>
        </div>

        <div class="clinical-action-box">
          <div class="action-title">💡 약사의 실전 대처 요령 & 처방 중재 가이드</div>
          <p>${r.clinical_action}</p>
        </div>
      </div>
    `).join('');

    showToast(`분석 완료: 총 ${data.interactions_found}건의 상호작용이 검출되었습니다.`, data.contraindicated_count > 0 ? 'error' : 'warning');
  } catch (err) {
    showToast('상호작용 검사 중 오류가 발생했습니다.', 'error');
  }
}

// ================= 탭 2: 병원 입지별 3단계 집중 감시 가이드 =================
async function loadHospitalGuides() {
  try {
    const res = await fetch('/api/hospital-guides');
    const data = await res.json();
    state.hospitalGuides = data.guides;

    renderHospitalNav();
    if (state.hospitalGuides.length > 0) {
      selectHospitalGuide(state.hospitalGuides[0].id);
    }
  } catch (err) {
    console.error('Failed to load guides', err);
  }
}

function renderHospitalNav() {
  const navContainer = document.getElementById('hospitalNav');
  navContainer.innerHTML = state.hospitalGuides.map(g => `
    <div class="hosp-btn ${state.selectedGuideId === g.id ? 'active' : ''}" data-id="${g.id}">
      <h3>${g.name}</h3>
      <span class="hosp-badge">${g.badge}</span>
    </div>
  `).join('');

  navContainer.querySelectorAll('.hosp-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-id');
      selectHospitalGuide(id);

      if (window.innerWidth <= 1024) {
        document.getElementById('hospitalDetailCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

// 병원 입지별 가이드 3단계 위험도(🚨 고위험 -> ⚠️ 경고 -> ℹ️ 주의) 계층 렌더링
function selectHospitalGuide(guideId) {
  state.selectedGuideId = guideId;
  renderHospitalNav();

  const guide = state.hospitalGuides.find(g => g.id === guideId);
  const detailCard = document.getElementById('hospitalDetailCard');
  if (!guide) return;

  // 신규 3단계 계층 시나리오 분리 (DANGER, WARNING, CAUTION)
  let scenariosHtml = '';
  if (guide.scenarios && guide.scenarios.length > 0) {
    const dangerList = guide.scenarios.filter(s => s.level === 'DANGER');
    const warningList = guide.scenarios.filter(s => s.level === 'WARNING');
    const cautionList = guide.scenarios.filter(s => s.level === 'CAUTION');

    const renderTierGroup = (title, levelClass, badgeText, items) => {
      if (!items || items.length === 0) return '';
      return `
        <div class="tier-section">
          <div class="tier-header ${levelClass}">
            <span>${title}</span>
            <span class="tier-badge-pill">${badgeText} (${items.length}건)</span>
          </div>
          <div class="tier-scenarios-list">
            ${items.map(sc => `
              <div class="tier-scenario-card">
                <div class="tier-card-title">💊 ${sc.combination}</div>
                <div class="tier-card-hazard"><strong>위험 핵심:</strong> ${sc.hazard}</div>
                <div class="tier-card-detail">${sc.detail}</div>
                <div class="tier-action-box">
                  <strong>💡 약사 대처 수칙:</strong> ${sc.action}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    };

    scenariosHtml = `
      <div class="tier-group-container">
        ${renderTierGroup('🚨 고위험 수준 (병용금기 및 치명적 위험)', 'danger', '치명적 금기', dangerList)}
        ${renderTierGroup('⚠️ 경고 수준 (주요 위험 / 면밀한 모니터링 필수)', 'warning', '집중 경고', warningList)}
        ${renderTierGroup('ℹ️ 주의 수준 (경미한 상호작용 / 생활요법 및 시간분리 지도)', 'caution', '복약 주의', cautionList)}
      </div>
    `;
  } else if (guide.high_risk_scenarios) {
    scenariosHtml = guide.high_risk_scenarios.map(sc => `
      <div class="hazard-card">
        <div class="hazard-title">${sc.hazard}</div>
        <div class="hazard-detail">${sc.detail}</div>
      </div>
    `).join('');
  }

  detailCard.innerHTML = `
    <div class="guide-detail-header">
      <h2>${guide.name}</h2>
      <span class="hosp-badge" style="margin-bottom:10px;">${guide.badge}</span>
      <p class="guide-desc">${guide.description}</p>
    </div>

    <div class="guide-section">
      <h4>🏥 입지별 위험도 3단계 계층 처방 충돌 시나리오</h4>
      ${scenariosHtml}
    </div>

    <div class="guide-section" style="margin-top:20px;">
      <h4>📋 약사 실전 처방전 검수 및 복약지도 체크리스트</h4>
      <div class="checklist-box">
        <ul>
          ${guide.pharmacist_checklist.map(chk => `
            <li>
              <span class="check-icon">✓</span>
              <span>${chk}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    </div>

    <div style="margin-top:20px; display:flex; gap:10px; flex-wrap:wrap;">
      <button class="btn btn-primary" onclick="openMemoModalWithDept('${guide.name}')">
        📝 이 입지 관련 약사 메모 작성하기
      </button>
    </div>
  `;
}

// ================= 탭 3: 방문 환자 관리 & 복약 상담 일지 =================
async function loadPatients(query = '') {
  try {
    const res = await fetch(`/api/patients${query ? `?q=${encodeURIComponent(query)}` : ''}`);
    const data = await res.json();
    state.patients = data.patients;
    document.getElementById('patientTotalCount').textContent = `${data.patients.length}명`;

    renderPatientList();
    if (state.selectedPatientId) {
      selectPatient(state.selectedPatientId);
    } else if (data.patients.length > 0) {
      selectPatient(data.patients[0].id);
    }
  } catch (err) {
    console.error('Failed to load patients', err);
  }
}

function renderPatientList() {
  const container = document.getElementById('patientListContainer');
  if (state.patients.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding:24px; color:#94a3b8;">등록된 환자가 없습니다.</div>';
    return;
  }

  container.innerHTML = state.patients.map(p => `
    <div class="patient-item ${state.selectedPatientId === p.id ? 'active' : ''}" data-id="${p.id}">
      <div class="patient-item-header">
        <span class="patient-name">${p.name} (${p.gender}, ${p.birth_year ? `${p.birth_year}년생` : '-'})</span>
        <span class="patient-chart-no">${p.chart_no}</span>
      </div>
      <div class="patient-chronic">${p.chronic_conditions || '기저질환 없음'}</div>
    </div>
  `).join('');

  container.querySelectorAll('.patient-item').forEach(item => {
    item.addEventListener('click', () => {
      const pid = parseInt(item.getAttribute('data-id'));
      selectPatient(pid);
    });
  });
}

async function selectPatient(patientId) {
  state.selectedPatientId = patientId;
  renderPatientList();

  const detailCard = document.getElementById('patientDetailCard');
  detailCard.innerHTML = '<div style="padding:32px; text-align:center; color:#0284c7;">환자 정보 및 방문 일지 로드 중...</div>';

  try {
    const res = await fetch(`/api/patients/${patientId}`);
    const data = await res.json();
    const p = data.patient;
    const visits = data.visits || [];

    detailCard.innerHTML = `
      <div class="patient-profile-header">
        <div>
          <h2>${p.name} <span style="font-size:0.875rem; color:#64748b;">(${p.gender}, ${p.birth_year}년생 / ${p.phone || '연락처 없음'})</span></h2>
          <span class="chart-tag">차트번호: ${p.chart_no}</span>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-primary" onclick="openVisitModal(${p.id})">📝 상담일지 작성 (약봉투 OCR)</button>
          <button class="btn btn-secondary" onclick="editPatient(${p.id})">수정</button>
        </div>
      </div>

      <div class="info-blocks-grid">
        <div class="info-block">
          <div class="info-block-title">기저 질환</div>
          <div class="info-block-content">${p.chronic_conditions || '등록된 기저질환 없음'}</div>
        </div>
        <div class="info-block">
          <div class="info-block-title">약물 알레르기 병력</div>
          <div class="info-block-content" style="color:#b91c1c; font-weight:600;">${p.allergies || '특이 알레르기 없음'}</div>
        </div>
        <div class="info-block" style="grid-column: 1/-1;">
          <div class="info-block-title">현재 정기 복용 중인 약물 목록</div>
          <div class="meds-chips-row">
            ${p.regular_meds && p.regular_meds.length > 0 
              ? p.regular_meds.map(m => `<span class="med-chip">💊 ${m}</span>`).join('') 
              : '<span style="color:#94a3b8; font-size:0.8125rem;">등록된 복용약 없음</span>'}
          </div>
          ${p.regular_meds && p.regular_meds.length > 0 ? `
            <button class="btn btn-secondary" style="margin-top:10px; font-size:0.75rem;" onclick="loadPatientMedsToDdiCheck('${p.name}', ${JSON.stringify(p.regular_meds).replace(/"/g, '&quot;')})">
              ⚡ 이 환자의 복용약을 상호작용 검사기로 일괄 전송
            </button>
          ` : ''}
        </div>
        ${p.special_notes ? `
          <div class="info-block" style="grid-column: 1/-1;">
            <div class="info-block-title">약사 특이 메모</div>
            <div class="info-block-content" style="background:#fffbeb; padding:10px; border-radius:6px; border:1px solid #fde68a;">
              ${p.special_notes}
            </div>
          </div>
        ` : ''}
      </div>

      <div class="visits-section">
        <div class="visits-header">
          <h3>📋 처방 조제 및 복약상담 기록 (${visits.length}건)</h3>
        </div>

        <div class="visits-timeline">
          ${visits.length === 0 ? '<div style="padding:24px; text-align:center; color:#94a3b8;">아직 작성된 상담 일지가 없습니다.</div>' : ''}
          ${visits.map(v => `
            <div class="visit-card">
              <div class="visit-top">
                <span class="visit-date">📅 ${v.visit_date}</span>
                <span class="visit-hospital">${v.hospital_name || '병원 미상'} [${v.hospital_dept || '진료과 미상'}]</span>
                <span style="font-size:0.75rem; color:#64748b; margin-left:auto;">👤 ${v.pharmacist_name || '담당약사'}</span>
              </div>
              <div class="visit-prescribed">
                <strong>처방 약물:</strong> ${v.prescribed_drugs}
              </div>
              ${v.prescription_image ? `
                <div style="margin-top:8px;">
                  <span style="font-size:0.75rem; color:#0284c7; font-weight:700;">📸 첨부된 약봉투 사진:</span><br>
                  <img src="${v.prescription_image}" style="max-height:120px; border-radius:6px; border:1px solid #cbd5e1; margin-top:4px;" alt="약봉투">
                </div>
              ` : ''}
              ${v.ddi_risk_summary ? `
                <div class="visit-hazard">
                  <strong>⚠️ 상호작용 경고:</strong> ${v.ddi_risk_summary}
                </div>
              ` : ''}
              <div class="visit-notes">
                <strong>약사 중재 및 상담 메모:</strong><br>
                ${v.counseling_notes ? v.counseling_notes.replace(/\n/g, '<br>') : '-'}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } catch (err) {
    console.error('Failed to select patient', err);
  }
}

// ================= 약봉투 사진 업로드 & 온프라미스 자체 OCR 엔진 로직 =================
function setupOcrListeners() {
  const triggerBtn = document.getElementById('btnTriggerBagUpload');
  const fileInput = document.getElementById('bagImageFileInput');
  const dropArea = document.getElementById('ocrDropArea');
  const runOcrBtn = document.getElementById('btnRunOcrAnalysis');
  const removeImgBtn = document.getElementById('btnRemoveBagImage');
  const applyBtn = document.getElementById('btnApplyMatchedDrugs');

  if (triggerBtn && fileInput) {
    triggerBtn.onclick = () => fileInput.click();
  }

  if (fileInput) {
    fileInput.onchange = (e) => {
      const file = e.target.files[0];
      if (file) handleBagImageFile(file);
    };
  }

  // 드래그 앤 드롭
  if (dropArea) {
    ['dragenter', 'dragover'].forEach(eventName => {
      dropArea.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropArea.classList.add('drag-active');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropArea.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropArea.classList.remove('drag-active');
      }, false);
    });

    dropArea.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const file = dt.files[0];
      if (file) handleBagImageFile(file);
    });
  }

  // 이미지 제거
  if (removeImgBtn) {
    removeImgBtn.onclick = () => {
      state.currentBagImageBase64 = null;
      document.getElementById('ocrPreviewContainer').style.display = 'none';
      document.getElementById('ocrResultsBox').style.display = 'none';
      document.getElementById('ocrProgressBox').style.display = 'none';
      document.querySelector('.ocr-drop-content').style.display = 'flex';
      if (fileInput) fileInput.value = '';
    };
  }

  // OCR 분석 시작 버튼
  if (runOcrBtn) {
    runOcrBtn.onclick = async () => {
      if (!state.currentBagImageBase64) {
        showToast('먼저 약봉투 사진을 업로드해주세요.', 'warning');
        return;
      }
      await runLocalOcrProcess(state.currentBagImageBase64);
    };
  }

  // 감지된 약물 처방 목록에 적용 버튼
  if (applyBtn) {
    applyBtn.onclick = () => {
      if (state.ocrMatchedDrugs.length === 0) {
        showToast('적용할 감지 약물이 없습니다.', 'info');
        return;
      }
      const names = state.ocrMatchedDrugs.map(d => `${d.name_ko} (${d.brand_names[0] || ''})`).join(', ');
      const prescribedInput = document.getElementById('vPrescribed');
      if (prescribedInput) {
        prescribedInput.value = names;
        showToast(`약봉투에서 감지된 ${state.ocrMatchedDrugs.length}개 약물이 처방 목록에 자동 입력되었습니다!`, 'success');
      }
    };
  }
}

function handleBagImageFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('이미지 파일(JPG, PNG 등)만 업로드할 수 있습니다.', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    state.currentBagImageBase64 = e.target.result;
    const previewImg = document.getElementById('bagImagePreview');
    const previewContainer = document.getElementById('ocrPreviewContainer');
    const dropContent = document.querySelector('.ocr-drop-content');

    if (previewImg && previewContainer) {
      previewImg.src = state.currentBagImageBase64;
      previewContainer.style.display = 'flex';
      if (dropContent) dropContent.style.display = 'none';
    }
  };
  reader.readAsDataURL(file);
}

// 브라우저 클라이언트 자체 Tesseract OCR 실행
async function runLocalOcrProcess(imageSrc) {
  const progressBox = document.getElementById('ocrProgressBox');
  const progressBar = document.getElementById('ocrProgressBar');
  const progressStatus = document.getElementById('ocrProgressStatus');
  const resultsBox = document.getElementById('ocrResultsBox');
  const extractedText = document.getElementById('ocrExtractedText');

  if (progressBox) progressBox.style.display = 'block';

  try {
    if (typeof Tesseract === 'undefined') {
      throw new Error('Tesseract.js OCR 엔진 로딩 대기 중...');
    }

    progressStatus.textContent = '온프라미스 브라우저 OCR 엔진 초기화 중...';
    progressBar.style.width = '10%';

    const result = await Tesseract.recognize(
      imageSrc,
      'kor+eng',
      {
        logger: m => {
          if (m.status === 'recognizing text') {
            const pct = Math.round((m.progress || 0) * 100);
            progressBar.style.width = `${pct}%`;
            progressStatus.textContent = `한글/영문 의약품 텍스트 광학 판독 중... (${pct}%)`;
          } else {
            progressStatus.textContent = `${m.status}...`;
          }
        }
      }
    );

    progressBar.style.width = '100%';
    progressStatus.textContent = '✅ 광학 판독 완료! 약물 데이터베이스 대조 중...';

    const text = result.data.text || '';
    if (extractedText) extractedText.value = text;
    if (resultsBox) resultsBox.style.display = 'block';

    // 서버 약물 DB와 매칭 API 호출
    await matchDrugsFromExtractedText(text);

  } catch (err) {
    console.error('OCR Error', err);
    progressStatus.textContent = '⚠️ OCR 분석 중 오류 발생: 텍스트를 직접 입력해주세요.';
    if (resultsBox) resultsBox.style.display = 'block';
    showToast('OCR 판독 실패: ' + err.message, 'error');
  }
}

// 판독된 텍스트에서 DB 약물 매칭
async function matchDrugsFromExtractedText(rawText) {
  try {
    const res = await fetch('/api/match-drugs-from-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: rawText })
    });
    const data = await res.json();
    const matched = data.matched_drugs || [];
    state.ocrMatchedDrugs = matched.map(m => m.drug);

    const chipsContainer = document.getElementById('matchedChipsList');
    if (!chipsContainer) return;

    if (matched.length === 0) {
      chipsContainer.innerHTML = '<span style="color:#64748b; font-size:0.775rem;">감지된 약물이 없습니다. 원문 텍스트를 확인해주세요.</span>';
      return;
    }

    chipsContainer.innerHTML = matched.map(m => `
      <span class="matched-chip">
        💊 ${m.drug.name_ko} (${m.matched_keyword})
      </span>
    `).join('');

    showToast(`약봉투에서 의약품 ${matched.length}건이 성공적으로 감지되었습니다!`, 'success');
  } catch (err) {
    console.error('Drug match error', err);
  }
}

// ================= 탭 4: 약사 전문 임상 메모 (다중 약사/파트타임 공유 및 코멘트) =================
async function loadMemos() {
  const query = document.getElementById('memoSearchInput').value.trim();
  const cat = document.getElementById('memoCategoryFilter').value;

  try {
    let url = '/api/memos?';
    if (query) url += `q=${encodeURIComponent(query)}&`;
    if (cat) url += `category=${encodeURIComponent(cat)}&`;

    const res = await fetch(url);
    const data = await res.json();
    state.memos = data.memos;

    renderMemos();
  } catch (err) {
    showToast('메모를 불러오지 못했습니다.', 'error');
  }
}

function renderMemos() {
  const container = document.getElementById('memoGridContainer');
  if (state.memos.length === 0) {
    container.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding:36px; color:#94a3b8;">작성된 임상 메모가 없습니다.</div>';
    return;
  }

  container.innerHTML = state.memos.map(m => {
    const comments = m.comments || [];
    return `
      <div class="memo-card ${m.is_pinned ? 'pinned' : ''}" data-id="${m.id}">
        <div>
          <div class="memo-card-header">
            <h3 class="memo-card-title">${m.title}</h3>
            ${m.is_pinned ? '<span class="pin-icon" title="상단 고정">📌</span>' : ''}
          </div>
          <div class="memo-meta-tags">
            <span class="memo-author-badge">👤 작성자: ${m.author_name || '대표약사'}</span>
            <span class="meta-category">${m.category}</span>
            ${m.hospital_dept ? `<span class="meta-dept">${m.hospital_dept}</span>` : ''}
            ${m.target_drugs ? `<span class="meta-dept" style="background:#fef3c7; color:#92400e;">💊 ${m.target_drugs}</span>` : ''}
          </div>
          <div class="memo-body">${m.content.replace(/\n/g, '<br>')}</div>
        </div>

        <!-- 다중 약사 협업 코멘트 타임라인 -->
        <div class="memo-comments-container">
          <div class="comments-toggle-header">
            <span>💬 다른 약사 의견 / 코멘트 (${comments.length}건)</span>
          </div>

          <div class="comments-list">
            ${comments.map(c => `
              <div class="comment-bubble">
                <div class="comment-header-row">
                  <span class="comment-author-name">👩‍⚕️ ${c.author_name}</span>
                  <span class="comment-created-time">${c.created_at ? c.created_at.substring(5, 16) : ''}</span>
                </div>
                <div class="comment-content-text">${c.comment_text}</div>
              </div>
            `).join('')}
          </div>

          <!-- 인라인 코멘트 추가 폼 -->
          <div class="add-comment-row">
            <select id="commentAuthor_${m.id}">
              <option value="오전 파트약사 (김약사)">오전 파트약사 (김약사)</option>
              <option value="오후 파트약사 (이약사)">오후 파트약사 (이약사)</option>
              <option value="주말 파트약사 (박약사)">주말 파트약사 (박약사)</option>
              <option value="대표약사">대표약사</option>
            </select>
            <input type="text" id="commentInput_${m.id}" placeholder="동료 약사 코멘트/피드백 남기기...">
            <button type="button" onclick="submitMemoComment(${m.id})">등록</button>
          </div>
        </div>

        <div class="memo-footer" style="margin-top:14px;">
          <span>🕒 ${m.created_at ? m.created_at.substring(0, 10) : ''}</span>
          <div class="memo-actions">
            <button class="btn-icon" onclick="deleteMemo(${m.id})" title="삭제">🗑️</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// 메모에 새 약사 코멘트 등록
window.submitMemoComment = async function(memoId) {
  const authorSelect = document.getElementById(`commentAuthor_${memoId}`);
  const inputEl = document.getElementById(`commentInput_${memoId}`);

  if (!inputEl || !inputEl.value.trim()) {
    showToast('코멘트 내용을 입력해주세요.', 'warning');
    return;
  }

  const authorName = authorSelect ? authorSelect.value : '파트약사';
  const commentText = inputEl.value.trim();

  try {
    const res = await fetch(`/api/memos/${memoId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        author_name: authorName,
        comment_text: commentText
      })
    });

    if (res.ok) {
      showToast('코멘트가 성공적으로 등록되었습니다.', 'success');
      inputEl.value = '';
      await loadMemos();
      await checkLatestActivity();
    } else {
      showToast('코멘트 등록 실패', 'error');
    }
  } catch (err) {
    showToast('코멘트 등록 중 오류 발생', 'error');
  }
};

async function deleteMemo(memoId) {
  if (!confirm('이 임상 메모를 삭제하시겠습니까?')) return;
  try {
    const res = await fetch(`/api/memos/${memoId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('메모가 삭제되었습니다.', 'success');
      loadMemos();
      loadStats();
    }
  } catch (err) {
    showToast('삭제 실패', 'error');
  }
}

// ================= 탭 5: 의약품 마스터 & DDI 규칙 사전 =================
async function loadRules() {
  try {
    const res = await fetch('/api/rules');
    const data = await res.json();
    state.rules = data.rules;
    renderRules();
  } catch (err) {
    console.error('Failed to load rules', err);
  }
}

function renderLibraryDrugs() {
  const container = document.getElementById('libDrugsTableBody');
  if (!container) return;
  const q = document.getElementById('libSearchInput')?.value.trim().toLowerCase() || '';

  const filtered = state.drugs.filter(d => {
    return !q ||
      d.name_ko.toLowerCase().includes(q) ||
      d.name_en.toLowerCase().includes(q) ||
      d.category.toLowerCase().includes(q) ||
      (d.brand_names && d.brand_names.some(b => b.toLowerCase().includes(q)));
  });

  container.innerHTML = filtered.map(d => `
    <tr>
      <td style="font-weight:700; color:#0f172a;">${d.name_ko}</td>
      <td style="color:#475569;">${d.name_en}</td>
      <td><span class="drug-badge">${d.category}</span></td>
      <td style="color:#0284c7; font-size:0.8125rem;">${d.brand_names ? d.brand_names.join(', ') : '-'}</td>
      <td style="font-size:0.775rem; color:#64748b;">${d.cyp_profile || d.class || '-'}</td>
    </tr>
  `).join('');
}

function renderRules() {
  const container = document.getElementById('libRulesCardList');
  if (!container) return;
  const q = document.getElementById('libSearchInput')?.value.trim().toLowerCase() || '';

  const filtered = state.rules.filter(r => {
    return !q ||
      r.title.toLowerCase().includes(q) ||
      r.mechanism.toLowerCase().includes(q) ||
      r.adverse_reactions.some(a => a.toLowerCase().includes(q)) ||
      r.clinical_action.toLowerCase().includes(q);
  });

  container.innerHTML = filtered.map(r => `
    <div class="ddi-card severity-${r.severity}">
      <div class="ddi-card-header">
        <div class="ddi-title">
          ${r.is_recent_sci ? '<span class="pill-recent-sci" style="margin-right:6px;">🔬 ' + (r.sci_badge || '최신 정보 (최근 2개년 SCI)') + '</span>' : ''}
          📖 ${r.title}
        </div>
        <span class="severity-pill pill-${r.severity}">${r.severity_ko}</span>
      </div>
      ${r.is_recent_sci ? `
        <div class="sci-evidence-banner">
          <div class="sci-badge-label">
            <span>🔬 최근 2개년 권위 SCI 논문 근거</span>
            <span>• ${r.sci_year || '2024'}</span>
          </div>
          <div class="sci-journal-info">📄 논문 출처: <strong>${r.sci_journal}</strong></div>
        </div>
      ` : ''}
      <div class="hospital-dept-tag">🏥 ${r.hospital_department || '종합/타과 복합'}</div>
      <div class="ddi-section">
        <div class="ddi-section-label">${r.is_recent_sci ? '🔬 약리학적 기전 및 최신 가설' : '기전'}</div>
        <div class="ddi-section-content">${r.mechanism}</div>
      </div>
      <div class="ddi-section">
        <div class="ddi-section-label">부작용</div>
        <ul class="adverse-list">
          ${r.adverse_reactions.map(a => `<li>${a}</li>`).join('')}
        </ul>
      </div>
      <div class="clinical-action-box">
        <div class="action-title">임상 대처 및 권고사항</div>
        <p>${r.clinical_action}</p>
      </div>
    </div>
  `).join('');
}

// ================= 이벤트 리스너 설정 =================
function setupEventListeners() {
  // 1. DDI 검사기 검색 & 필터
  const drugSearch = document.getElementById('drugSearchInput');
  if (drugSearch) drugSearch.addEventListener('input', renderDrugList);

  const drugCat = document.getElementById('drugCategoryFilter');
  if (drugCat) drugCat.addEventListener('change', renderDrugList);

  const btnCheck = document.getElementById('btnRunDdiCheck');
  if (btnCheck) btnCheck.addEventListener('click', runDdiCheck);

  const btnClear = document.getElementById('btnClearSelected');
  if (btnClear) btnClear.addEventListener('click', () => {
    state.selectedDrugIds.clear();
    updateSelectedTagsBox();
    renderDrugList();
    document.getElementById('ddiResultContainer').innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🩺</div>
        <h3>선택이 초기화되었습니다</h3>
        <p>왼쪽 목록에서 상호작용을 검사할 약물을 2개 이상 선택해주세요.</p>
      </div>
    `;
    document.getElementById('resultSummaryBadges').innerHTML = '';
  });

  // 빠른 샘플 버튼들
  document.querySelectorAll('.btn-sample').forEach(btn => {
    btn.addEventListener('click', () => {
      const sample = btn.getAttribute('data-sample');
      if (!sample) return;
      const ids = sample.split(',');
      state.selectedDrugIds.clear();
      ids.forEach(id => state.selectedDrugIds.add(id.trim()));
      updateSelectedTagsBox();
      renderDrugList();
      runDdiCheck();
    });
  });

  // 2. 환자 검색
  const pSearch = document.getElementById('patientSearchInput');
  if (pSearch) {
    pSearch.addEventListener('input', (e) => {
      loadPatients(e.target.value.trim());
    });
  }

  // 3. 메모 검색 & 필터
  const mSearch = document.getElementById('memoSearchInput');
  if (mSearch) mSearch.addEventListener('input', loadMemos);

  const mCat = document.getElementById('memoCategoryFilter');
  if (mCat) mCat.addEventListener('change', loadMemos);

  // 4. 모달 열기/닫기
  setupModalTriggers();

  // 5. 공지사항 토글
  const toggleBtn = document.getElementById('btnToggleSciNotice');
  const noticeHeader = document.getElementById('sciNoticeToggle');
  const noticeBody = document.getElementById('sciNoticeBody');
  const toggleIcon = document.getElementById('sciToggleIcon');

  if (toggleBtn && noticeBody) {
    const doToggle = () => {
      const isHidden = noticeBody.style.display === 'none';
      noticeBody.style.display = isHidden ? 'block' : 'none';
      if (toggleIcon) toggleIcon.textContent = isHidden ? '▼' : '▲';
    };
    toggleBtn.addEventListener('click', (e) => { e.stopPropagation(); doToggle(); });
    if (noticeHeader) noticeHeader.addEventListener('click', doToggle);
  }

  // 사전 서브탭 전환
  document.querySelectorAll('.lib-subtab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lib-subtab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.library-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.getAttribute('data-subtab');
      document.getElementById(target)?.classList.add('active');
    });
  });

  const libSearch = document.getElementById('libSearchInput');
  if (libSearch) {
    libSearch.addEventListener('input', () => {
      renderLibraryDrugs();
      renderRules();
    });
  }
}

// 모달 제어
function setupModalTriggers() {
  // 모바일 접속 안내 모달
  const openMobileBtn = document.getElementById('btnOpenMobileConnectModal');
  const closeMobileBtn = document.getElementById('btnCloseMobileConnectModal');
  const closeMobileBtn2 = document.getElementById('btnCloseMobileConnectModal2');
  const mobileModal = document.getElementById('mobileConnectModal');

  if (openMobileBtn && mobileModal) {
    openMobileBtn.addEventListener('click', () => mobileModal.classList.add('active'));
  }
  if (closeMobileBtn && mobileModal) {
    closeMobileBtn.addEventListener('click', () => mobileModal.classList.remove('active'));
  }
  if (closeMobileBtn2 && mobileModal) {
    closeMobileBtn2.addEventListener('click', () => mobileModal.classList.remove('active'));
  }

  const copyUrlBtn = document.getElementById('btnCopyMobileUrl');
  if (copyUrlBtn) {
    copyUrlBtn.addEventListener('click', () => {
      const input = document.getElementById('mobileAccessUrlInput');
      if (input) {
        navigator.clipboard.writeText(input.value);
        showToast('접속 URL이 클립보드에 복사되었습니다.', 'success');
      }
    });
  }

  // 신규 환자 모달
  const openPatientBtn = document.getElementById('btnOpenNewPatientModal');
  const closePatientBtn = document.getElementById('btnClosePatientModal');
  const cancelPatientBtn = document.getElementById('btnCancelPatient');
  const patientModal = document.getElementById('patientModal');
  const patientForm = document.getElementById('patientForm');

  if (openPatientBtn && patientModal) {
    openPatientBtn.addEventListener('click', () => {
      patientForm.reset();
      document.getElementById('pFormId').value = '';
      document.getElementById('patientModalTitle').textContent = '신규 환자 등록';
      patientModal.classList.add('active');
    });
  }
  if (closePatientBtn && patientModal) {
    closePatientBtn.addEventListener('click', () => patientModal.classList.remove('active'));
  }
  if (cancelPatientBtn && patientModal) {
    cancelPatientBtn.addEventListener('click', () => patientModal.classList.remove('active'));
  }

  if (patientForm) {
    patientForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pid = document.getElementById('pFormId').value;
      const isEdit = !!pid;

      const regularMedsRaw = document.getElementById('pFormRegularMeds').value;
      const regularMedsList = regularMedsRaw.split(',').map(m => m.trim()).filter(Boolean);

      const payload = {
        name: document.getElementById('pFormName').value.trim(),
        birth_year: document.getElementById('pFormBirthYear').value.trim(),
        gender: document.getElementById('pFormGender').value,
        phone: document.getElementById('pFormPhone').value.trim(),
        chart_no: document.getElementById('pFormChartNo').value.trim(),
        chronic_conditions: document.getElementById('pFormChronic').value.trim(),
        allergies: document.getElementById('pFormAllergies').value.trim(),
        regular_meds: regularMedsList,
        special_notes: document.getElementById('pFormNotes').value.trim()
      };

      try {
        const url = isEdit ? `/api/patients/${pid}` : '/api/patients';
        const method = isEdit ? 'PUT' : 'POST';
        const res = await fetch(url, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          showToast(isEdit ? '환자 정보가 수정되었습니다.' : '환자가 등록되었습니다.', 'success');
          patientModal.classList.remove('active');
          await loadPatients();
          await loadStats();
          await checkLatestActivity();
        } else {
          showToast('저장에 실패했습니다.', 'error');
        }
      } catch (err) {
        showToast('서버 통신 오류', 'error');
      }
    });
  }

  // 방문 상담 일지 모달
  const closeVisitBtn = document.getElementById('btnCloseVisitModal');
  const cancelVisitBtn = document.getElementById('btnCancelVisit');
  const visitModal = document.getElementById('visitModal');
  const visitForm = document.getElementById('visitForm');

  if (closeVisitBtn && visitModal) {
    closeVisitBtn.addEventListener('click', () => visitModal.classList.remove('active'));
  }
  if (cancelVisitBtn && visitModal) {
    cancelVisitBtn.addEventListener('click', () => visitModal.classList.remove('active'));
  }

  if (visitForm) {
    visitForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pid = document.getElementById('vPatientId').value;
      if (!pid) return;

      const payload = {
        visit_date: document.getElementById('vDate').value,
        hospital_name: document.getElementById('vHospitalName').value.trim(),
        hospital_dept: document.getElementById('vHospitalDept').value,
        pharmacist_name: document.getElementById('vPharmacistName').value,
        prescribed_drugs: document.getElementById('vPrescribed').value.trim(),
        ddi_risk_summary: document.getElementById('vRiskSummary').value.trim(),
        counseling_notes: document.getElementById('vCounselingNotes').value.trim(),
        prescription_image: state.currentBagImageBase64 || '',
        ocr_raw_text: document.getElementById('ocrExtractedText')?.value || ''
      };

      try {
        const res = await fetch(`/api/patients/${pid}/visits`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          showToast('상담 및 조제 기록(새 기록지)이 성공적으로 저장되었습니다.', 'success');
          visitModal.classList.remove('active');
          selectPatient(pid);
          await loadStats();
          await checkLatestActivity();
        } else {
          showToast('저장에 실패했습니다.', 'error');
        }
      } catch (err) {
        showToast('서버 통신 오류', 'error');
      }
    });
  }

  // 임상 메모 모달
  const openMemoBtn = document.getElementById('btnOpenNewMemoModal');
  const closeMemoBtn = document.getElementById('btnCloseMemoModal');
  const cancelMemoBtn = document.getElementById('btnCancelMemo');
  const memoModal = document.getElementById('memoModal');
  const memoForm = document.getElementById('memoForm');
  const authorSelect = document.getElementById('mFormAuthor');
  const customAuthorInput = document.getElementById('mFormAuthorCustom');

  if (authorSelect && customAuthorInput) {
    authorSelect.addEventListener('change', () => {
      customAuthorInput.style.display = authorSelect.value === 'custom' ? 'block' : 'none';
    });
  }

  if (openMemoBtn && memoModal) {
    openMemoBtn.addEventListener('click', () => {
      memoForm.reset();
      document.getElementById('memoFormId').value = '';
      if (customAuthorInput) customAuthorInput.style.display = 'none';
      document.getElementById('memoModalTitle').textContent = '새 임상 메모 작성';
      memoModal.classList.add('active');
    });
  }
  if (closeMemoBtn && memoModal) {
    closeMemoBtn.addEventListener('click', () => memoModal.classList.remove('active'));
  }
  if (cancelMemoBtn && memoModal) {
    cancelMemoBtn.addEventListener('click', () => memoModal.classList.remove('active'));
  }

  if (memoForm) {
    memoForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const mid = document.getElementById('memoFormId').value;
      const isEdit = !!mid;

      let authorName = authorSelect.value;
      if (authorName === 'custom') {
        authorName = customAuthorInput.value.trim() || '파트약사';
      }

      const payload = {
        title: document.getElementById('mFormTitle').value.trim(),
        author_name: authorName,
        category: document.getElementById('mFormCategory').value,
        target_drugs: document.getElementById('mFormDrugs').value.trim(),
        hospital_dept: document.getElementById('mFormDept').value.trim(),
        content: document.getElementById('mFormContent').value.trim(),
        tags: document.getElementById('mFormTags').value.trim(),
        is_pinned: document.getElementById('mFormPinned').checked
      };

      try {
        const url = isEdit ? `/api/memos/${mid}` : '/api/memos';
        const method = isEdit ? 'PUT' : 'POST';
        const res = await fetch(url, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          showToast(isEdit ? '메모가 수정되었습니다.' : '약사 임상 메모(새 기록지)가 등록되었습니다.', 'success');
          memoModal.classList.remove('active');
          await loadMemos();
          await loadStats();
          await checkLatestActivity();
        } else {
          showToast('저장에 실패했습니다.', 'error');
        }
      } catch (err) {
        showToast('서버 통신 오류', 'error');
      }
    });
  }
}

// 전역 헬퍼 함수들
window.openVisitModal = function(patientId) {
  const visitForm = document.getElementById('visitForm');
  if (visitForm) visitForm.reset();

  document.getElementById('vPatientId').value = patientId;
  document.getElementById('vDate').value = new Date().toISOString().substring(0, 10);

  // 약봉투 이미지 상태 초기화
  state.currentBagImageBase64 = null;
  state.ocrMatchedDrugs = [];
  const preview = document.getElementById('ocrPreviewContainer');
  const results = document.getElementById('ocrResultsBox');
  const progress = document.getElementById('ocrProgressBox');
  const dropContent = document.querySelector('.ocr-drop-content');

  if (preview) preview.style.display = 'none';
  if (results) results.style.display = 'none';
  if (progress) progress.style.display = 'none';
  if (dropContent) dropContent.style.display = 'flex';

  document.getElementById('visitModal').classList.add('active');
};

window.editPatient = function(patientId) {
  const p = state.patients.find(x => x.id === patientId);
  if (!p) return;

  document.getElementById('pFormId').value = p.id;
  document.getElementById('pFormName').value = p.name;
  document.getElementById('pFormBirthYear').value = p.birth_year || '';
  document.getElementById('pFormGender').value = p.gender || '기타';
  document.getElementById('pFormPhone').value = p.phone || '';
  document.getElementById('pFormChartNo').value = p.chart_no || '';
  document.getElementById('pFormChronic').value = p.chronic_conditions || '';
  document.getElementById('pFormAllergies').value = p.allergies || '';
  document.getElementById('pFormRegularMeds').value = p.regular_meds ? p.regular_meds.join(', ') : '';
  document.getElementById('pFormNotes').value = p.special_notes || '';

  document.getElementById('patientModalTitle').textContent = '환자 정보 수정';
  document.getElementById('patientModal').classList.add('active');
};

window.openMemoModalWithDept = function(deptName) {
  const memoModal = document.getElementById('memoModal');
  const memoForm = document.getElementById('memoForm');
  memoForm.reset();
  document.getElementById('memoFormId').value = '';
  document.getElementById('mFormCategory').value = '병원입지별 주의';
  document.getElementById('mFormDept').value = deptName;
  document.getElementById('mFormTitle').value = `[${deptName}] 집중 처방 검수 메모`;
  document.getElementById('memoModalTitle').textContent = '새 임상 메모 작성';
  memoModal.classList.add('active');
};

window.loadPatientMedsToDdiCheck = function(patientName, medsArray) {
  if (!medsArray || medsArray.length === 0) return;
  state.selectedDrugIds.clear();

  let matchedCount = 0;
  medsArray.forEach(medText => {
    const cleanText = medText.toLowerCase();
    const found = state.drugs.find(d => 
      cleanText.includes(d.name_ko.toLowerCase()) || 
      cleanText.includes(d.name_en.toLowerCase()) ||
      d.brand_names.some(b => cleanText.includes(b.split('(')[0].toLowerCase()))
    );
    if (found) {
      state.selectedDrugIds.add(found.id);
      matchedCount++;
    }
  });

  const ddiTabBtn = document.querySelector('[data-tab="tab-ddi"]');
  if (ddiTabBtn) ddiTabBtn.click();

  updateSelectedTagsBox();
  renderDrugList();

  showToast(`${patientName} 님의 복용약 ${matchedCount}개가 검사기에 자동 등록되었습니다. 추가 처방약을 선택 후 검사하세요!`, 'success');
};

// SVG QR 코드 렌더링
function renderQrCode(url) {
  const container = document.getElementById('qrContainer');
  if (!container) return;
  const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(url)}&color=0284c7`;
  container.innerHTML = `
    <img src="${qrApiUrl}" alt="모바일 접속 QR 코드" style="width:160px; height:160px; border-radius:10px; border:1px solid #cbd5e1; box-shadow:0 4px 6px rgba(0,0,0,0.05);" />
  `;
}

// 토스트 메시지
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ================= 한국형 DDInter 지식 지속 축적 & GitHub 자동 동기화 =================

// 1. Git 동기화 상태 조회 및 UI 업데이트
async function loadGitSyncStatus() {
  try {
    const res = await fetch('/api/git-sync-status');
    if (!res.ok) return;
    const data = await res.json();
    state.gitSync = data;

    // 헤더 상태 인디케이터 갱신
    const dot = document.getElementById('headerSyncDot');
    const txt = document.getElementById('headerSyncStatusText');
    if (dot) {
      if (data.is_syncing) {
        dot.className = 'status-dot syncing';
      } else {
        dot.className = 'status-dot active';
      }
    }
    if (txt) {
      txt.textContent = data.is_syncing ? 'GitHub 푸시 중...' : 'GitHub 자동 동기화 됨';
    }

    // DDInter 탭 상태 갱신
    const statDrugs = document.getElementById('ddinterStatDrugs');
    const statRules = document.getElementById('ddinterStatRules');
    const commitHash = document.getElementById('ddinterCommitHash');
    const syncStatusText = document.getElementById('ddinterSyncStatusText');
    const lastSyncTime = document.getElementById('ddinterLastSyncTime');
    const badgeStatus = document.getElementById('gitSyncBadgeStatus');

    if (statDrugs) statDrugs.textContent = `${data.total_drugs || 516}종`;
    if (statRules) statRules.textContent = `${data.total_rules || 766}건`;
    if (commitHash) commitHash.textContent = `Commit: ${data.commit_hash || '4e0ed1a'} (${data.branch || 'main'})`;
    if (syncStatusText) {
      syncStatusText.textContent = data.is_syncing ? '동기화 푸시 진행 중...' : '원격 자동 푸시 활성';
      syncStatusText.className = data.is_syncing ? 'stat-number warning' : 'stat-number active';
    }
    if (lastSyncTime) {
      lastSyncTime.textContent = data.commit_time ? `최근 커밋: ${data.commit_time}` : '실시간 큐 작동 중';
    }
    if (badgeStatus) {
      badgeStatus.textContent = data.is_syncing ? '동기화 중...' : `연결됨 (${data.branch || 'main'})`;
      badgeStatus.className = data.is_syncing ? 'badge badge-warning' : 'badge badge-success';
    }

    // Git 커밋 히스토리 타임라인 렌더링
    if (data.recent_commits) {
      renderGitLogTimeline(data.recent_commits);
    }
  } catch (err) {
    console.error('Failed to load git sync status', err);
  }
}

// 2. 수동 GitHub 즉시 동기화 실행
async function triggerGitSyncNow() {
  const btnHeader = document.getElementById('btnHeaderGitSync');
  const btnHero = document.getElementById('btnDdinterSyncNow');
  if (btnHeader) btnHeader.disabled = true;
  if (btnHero) btnHero.disabled = true;

  showToast('GitHub 원격 저장소(ralf-kang/Pharm-DDI)로 수동 즉시 동기화를 시작합니다...', 'info');

  try {
    const res = await fetch('/api/git-sync-now', { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`GitHub 원격 저장소에 성공적으로 동기화되었습니다! (커밋: ${data.commit_hash || 'OK'})`, 'success');
      await loadGitSyncStatus();
      await loadStats();
    } else {
      showToast(`동기화 알림: ${data.error || '잠시 후 다시 시도해주세요.'}`, 'warning');
    }
  } catch (err) {
    showToast('GitHub 동기화 서버 통신 실패', 'error');
  } finally {
    if (btnHeader) btnHeader.disabled = false;
    if (btnHero) btnHero.disabled = false;
  }
}

// 3. DDInter 탭 이벤트 리스너 설정
function setupDdinterListeners() {
  // 헤더 즉시 동기화 버튼
  const btnHeader = document.getElementById('btnHeaderGitSync');
  if (btnHeader) {
    btnHeader.addEventListener('click', triggerGitSyncNow);
  }

  // Hero 섹션 즉시 동기화 버튼
  const btnHero = document.getElementById('btnDdinterSyncNow');
  if (btnHero) {
    btnHero.addEventListener('click', triggerGitSyncNow);
  }

  // 신규 의약품 모달 열기/닫기
  const btnOpenDrug = document.getElementById('btnOpenAddDrugModal');
  const btnCloseDrug = document.getElementById('btnCloseAddDrugModal');
  const btnCancelDrug = document.getElementById('btnCancelAddDrug');
  const modalDrug = document.getElementById('addDrugModal');

  if (btnOpenDrug) btnOpenDrug.addEventListener('click', openAddDrugModal);
  if (btnCloseDrug && modalDrug) btnCloseDrug.addEventListener('click', () => modalDrug.classList.remove('active'));
  if (btnCancelDrug && modalDrug) btnCancelDrug.addEventListener('click', () => modalDrug.classList.remove('active'));

  // 신규 DDI 규칙 모달 열기/닫기
  const btnOpenRule = document.getElementById('btnOpenAddRuleModal');
  const btnCloseRule = document.getElementById('btnCloseAddRuleModal');
  const btnCancelRule = document.getElementById('btnCancelAddRule');
  const modalRule = document.getElementById('addRuleModal');

  if (btnOpenRule) btnOpenRule.addEventListener('click', openAddRuleModal);
  if (btnCloseRule && modalRule) btnCloseRule.addEventListener('click', () => modalRule.classList.remove('active'));
  if (btnCancelRule && modalRule) btnCancelRule.addEventListener('click', () => modalRule.classList.remove('active'));

  // 폼 제출 리스너
  const formDrug = document.getElementById('addDrugForm');
  if (formDrug) formDrug.addEventListener('submit', handleAddDrugSubmit);

  const formRule = document.getElementById('addRuleForm');
  if (formRule) formRule.addEventListener('submit', handleAddRuleSubmit);

  // 실시간 검색
  const searchInput = document.getElementById('ddinterSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      renderDdinterKnowledge();
    });
  }
}

// 4. 신규 의약품 모달 열기
function openAddDrugModal() {
  const form = document.getElementById('addDrugForm');
  if (form) form.reset();
  const modal = document.getElementById('addDrugModal');
  if (modal) modal.classList.add('active');
}

// 5. 신규 DDI 규칙 모달 열기 (약물 셀렉트박스 옵션 채우기)
function openAddRuleModal() {
  const form = document.getElementById('addRuleForm');
  if (form) form.reset();

  const selA = document.getElementById('rFormDrugA');
  const selB = document.getElementById('rFormDrugB');

  if (selA && selB) {
    const sorted = [...state.drugs].sort((a, b) => a.name_ko.localeCompare(b.name_ko, 'ko'));
    const optionsHtml = sorted.map(d => `<option value="${d.id}">${d.name_ko} (${d.name_en}) - ${d.category}</option>`).join('');

    selA.innerHTML = '<option value="">약물 1 선택...</option>' + optionsHtml;
    selB.innerHTML = '<option value="">약물 2 선택...</option>' + optionsHtml;
  }

  const modal = document.getElementById('addRuleModal');
  if (modal) modal.classList.add('active');
}

// 6. 신규 의약품 등록 처리 (Git 자동 축적 큐 등록)
async function handleAddDrugSubmit(e) {
  e.preventDefault();
  const modal = document.getElementById('addDrugModal');

  const brandsRaw = document.getElementById('dFormBrands').value.trim();
  const brandsList = brandsRaw ? brandsRaw.split(',').map(b => b.trim()).filter(Boolean) : [];

  const payload = {
    id: document.getElementById('dFormId').value.trim(),
    name_ko: document.getElementById('dFormKo').value.trim(),
    name_en: document.getElementById('dFormEn').value.trim(),
    category: document.getElementById('dFormCat').value,
    class: document.getElementById('dFormClass').value.trim(),
    brand_names: brandsList,
    cyp_profile: document.getElementById('dFormCyp').value.trim()
  };

  try {
    const res = await fetch('/api/drugs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(`'${payload.name_ko}' 의약품이 성공적으로 등록되었으며 data/drugs.json 및 GitHub 원격 축적 큐에 등록되었습니다.`, 'success');
      if (modal) modal.classList.remove('active');
      await loadDrugs();
      await loadStats();
      await loadGitSyncStatus();
      renderDdinterView();
    } else {
      showToast(`등록 실패: ${data.error || '입력값을 확인해주세요.'}`, 'error');
    }
  } catch (err) {
    showToast('서버 통신 실패', 'error');
  }
}

// 7. 신규 DDI 규칙 등록 처리 (Git 자동 축적 큐 등록)
async function handleAddRuleSubmit(e) {
  e.preventDefault();
  const modal = document.getElementById('addRuleModal');

  const drugA = document.getElementById('rFormDrugA').value;
  const drugB = document.getElementById('rFormDrugB').value;

  if (drugA === drugB) {
    showToast('동일한 약물을 상호작용 쌍으로 선택할 수 없습니다.', 'warning');
    return;
  }

  const adverseRaw = document.getElementById('rFormAdverse').value.trim();
  const adverseList = adverseRaw ? adverseRaw.split(',').map(a => a.trim()).filter(Boolean) : [];

  const payload = {
    drug_a_id: drugA,
    drug_b_id: drugB,
    severity: document.getElementById('rFormSeverity').value,
    title: document.getElementById('rFormTitle').value.trim(),
    mechanism: document.getElementById('rFormMechanism').value.trim(),
    adverse_reactions: adverseList,
    clinical_action: document.getElementById('rFormAction').value.trim(),
    hospital_department: document.getElementById('rFormDept').value.trim() || '종합/타과 복합'
  };

  try {
    const res = await fetch('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast(`'${payload.title}' DDI 규칙이 등록되었으며 data/rules.json 및 GitHub 원격 축적 큐에 등록되었습니다.`, 'success');
      if (modal) modal.classList.remove('active');
      await loadRules();
      await loadStats();
      await loadGitSyncStatus();
      renderDdinterView();
    } else {
      showToast(`등록 실패: ${data.error || '입력값을 확인해주세요.'}`, 'error');
    }
  } catch (err) {
    showToast('서버 통신 실패', 'error');
  }
}

// 8. DDInter 탭 메인 렌더링
function renderDdinterView() {
  loadGitSyncStatus();
  renderDdinterKnowledge();
}

// 9. 축적 지식 브라우저 카드 렌더링
function renderDdinterKnowledge() {
  const container = document.getElementById('ddinterKnowledgeList');
  if (!container) return;

  const query = document.getElementById('ddinterSearchInput')?.value.trim().toLowerCase() || '';

  // 최근 규칙 중 검색 필터링
  const filtered = state.rules.filter(r => {
    if (!query) return true;
    return (
      r.title.toLowerCase().includes(query) ||
      r.mechanism.toLowerCase().includes(query) ||
      r.clinical_action.toLowerCase().includes(query) ||
      (r.adverse_reactions && r.adverse_reactions.some(a => a.toLowerCase().includes(query)))
    );
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 40px 20px;">
        <div class="empty-icon">🔍</div>
        <h3>검색 조건과 일치하는 축적 지식이 없습니다</h3>
        <p>'${query}' 키워드를 변경하거나 상단 '+ 신규 DDI 규칙 등록' 버튼으로 새 지식을 축적하세요.</p>
      </div>
    `;
    return;
  }

  // 상위 50개 렌더링
  const displayList = filtered.slice(0, 50);

  container.innerHTML = displayList.map(r => {
    const drugA = state.drugs.find(d => d.id === r.drug_a_id);
    const drugB = state.drugs.find(d => d.id === r.drug_b_id);

    return `
      <div class="ddinter-knowledge-card severity-${r.severity}">
        <div class="knowledge-card-header">
          <div class="knowledge-title-row">
            <span class="severity-pill pill-${r.severity}">${r.severity_ko || r.severity}</span>
            <strong class="knowledge-title">${r.title}</strong>
            ${r.is_recent_sci ? '<span class="pill-recent-sci">🔬 최신 SCI</span>' : ''}
          </div>
          <span class="git-source-tag">Git Versioned • data/rules.json</span>
        </div>

        <div class="knowledge-drug-pair">
          <span class="drug-chip-a">💊 ${drugA ? `${drugA.name_ko} (${drugA.name_en})` : r.drug_a_id}</span>
          <span class="pair-cross">✖️</span>
          <span class="drug-chip-b">💊 ${drugB ? `${drugB.name_ko} (${drugB.name_en})` : r.drug_b_id}</span>
          ${r.hospital_department ? `<span class="dept-tag">🏥 ${r.hospital_department}</span>` : ''}
        </div>

        <div class="knowledge-body-grid">
          <div class="knowledge-prop-box">
            <span class="prop-label">🧬 약동/약력학 상호작용 기전</span>
            <p class="prop-text">${r.mechanism}</p>
          </div>
          <div class="knowledge-prop-box">
            <span class="prop-label">⚠️ 발생 가능 주요 부작용</span>
            <div class="adverse-chips">
              ${(r.adverse_reactions || []).map(a => `<span class="adverse-chip">${a}</span>`).join('')}
            </div>
          </div>
        </div>

        <div class="knowledge-action-box">
          <span class="action-label">📋 약사의 임상 조치 및 복약지도 가이드</span>
          <p class="action-text">${r.clinical_action}</p>
        </div>
      </div>
    `;
  }).join('');
}

// 10. Git 커밋 타임라인 렌더링
function renderGitLogTimeline(commits) {
  const container = document.getElementById('gitLogTimeline');
  if (!container) return;

  if (!commits || commits.length === 0) {
    container.innerHTML = `
      <div class="git-log-item">
        <div class="log-hash">Init</div>
        <div class="log-msg">GitHub 원격 저장소 동기화 대기 중</div>
        <div class="log-meta">ralf-kang/Pharm-DDI</div>
      </div>
    `;
    return;
  }

  container.innerHTML = commits.map(c => `
    <div class="git-log-item">
      <div class="log-item-header">
        <span class="log-hash">#${c.hash || 'commit'}</span>
        <span class="log-date">${c.date || ''}</span>
      </div>
      <div class="log-msg">${c.message || 'Data accumulation commit'}</div>
      <div class="log-meta">
        <span>👤 ${c.author || 'Pharm-DDI Engine'}</span>
        <span class="branch-tag">origin/main</span>
      </div>
    </div>
  `).join('');
}
