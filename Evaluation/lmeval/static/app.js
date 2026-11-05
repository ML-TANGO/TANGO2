/* LM-Eval 벤치마크 평가 대시보드 — vanilla JS (외부 CDN 없음) */
'use strict';

const $ = (id) => document.getElementById(id);
const FIELDS = ['model_path', 'run_dir', 'seed', 'gpus', 'batch_size', 'max_length',
  'limit', 'num_fewshot', 'dtype', 'custom_lang', 'custom_file',
  'custom_max_new_tokens', 'custom_system_prompt'];
const CHECKS = ['apply_chat_template', 'fewshot_as_multiturn', 'log_samples', 'parallelize'];
const GROUP_COLOR = { core_en: 'b', korean: 'g', generative: 'p', custom: 'a' };
const GROUP_HEX = { core_en: '#60a5fa', korean: '#4ade80', generative: '#c4b5fd', custom: '#fbbf24' };

let REGISTRY = null;
let DEFAULTS = {};
let MODELS = { models: [], hf_token: false };
let pollTimer = null;

/* ------------------------------------------------------------------ 설정 */
function collectConfig() {
  const cfg = {};
  FIELDS.forEach((f) => { const el = $(f); if (el) cfg[f] = el.value; });
  CHECKS.forEach((f) => { cfg[f] = $(f).checked; });
  cfg.seed = parseInt(cfg.seed || '42', 10);
  cfg.max_length = parseInt(cfg.max_length || '4096', 10);
  cfg.custom_max_new_tokens = parseInt(cfg.custom_max_new_tokens || '256', 10);
  cfg.limit = (cfg.limit === '' ? '' : parseInt(cfg.limit, 10));
  cfg.tasks = [...document.querySelectorAll('.taskchk:checked')].map((c) => c.value);
  return cfg;
}

function applyConfig(cfg) {
  FIELDS.forEach((f) => {
    const el = $(f);
    if (el && cfg[f] !== undefined && cfg[f] !== null) el.value = cfg[f];
  });
  CHECKS.forEach((f) => { $(f).checked = !!cfg[f]; });
  const sel = new Set(cfg.tasks || []);
  document.querySelectorAll('.taskchk').forEach((c) => { c.checked = sel.has(c.value); });
  syncPreset();
}

/* --------------------------------------------------------------- 모델 선택 */
function renderModelPresets() {
  const sl = $('model_preset');
  sl.innerHTML = '';
  MODELS.models.forEach((m) => {
    const o = document.createElement('option');
    o.value = m.repo_id;
    o.textContent = `${m.label} — ${m.repo_id}` +
      (m.cached ? `  ✓ 캐시 (${m.size_text})` : '  ⬇ 다운로드 필요') +
      (m.gated ? '  🔒' : '');
    o.title = m.note || '';
    sl.appendChild(o);
  });
  const o = document.createElement('option');
  o.value = '__custom__';
  o.textContent = '직접 입력 (repo id 또는 로컬 경로) …';
  sl.appendChild(o);
}

/** MODEL_PATH 값에 맞춰 드롭다운 선택 상태를 맞춘다. */
function syncPreset() {
  const cur = ($('model_path').value || '').trim();
  const hit = MODELS.models.some((m) => m.repo_id === cur);
  $('model_preset').value = hit ? cur : '__custom__';
  $('modelPathFld').style.display = hit ? 'none' : '';
}

function onPresetChange() {
  const v = $('model_preset').value;
  if (v === '__custom__') {
    $('modelPathFld').style.display = '';
    $('model_path').focus();
    return;
  }
  const m = MODELS.models.find((x) => x.repo_id === v);
  $('model_path').value = v;
  $('modelPathFld').style.display = 'none';
  // RUN_DIR 이 다른 모델의 기본값이면 함께 바꿔 준다(직접 지정한 값은 보존).
  const known = MODELS.models.map((x) => x.run_dir);
  const cur = ($('run_dir').value || '').trim();
  if (m && m.run_dir && (cur === '' || known.includes(cur))) $('run_dir').value = m.run_dir;
  refreshDerived();
}

function renderModelStat(d) {
  const m = (d && d.model) || null;
  const box = $('modelStat');
  if (!m) { box.textContent = '-'; box.className = 'modelstat'; return; }
  const state = m.cached ? 'ok' : (m.ready ? 'warn' : 'err');
  const size = m.cached ? ` · ${m.size_text}` : '';
  const tok = m.gated && !m.hf_token ? ' · HF_TOKEN 없음' : '';
  box.className = 'modelstat ' + state;
  box.textContent = `${m.cached ? '✓' : (m.ready ? '⬇' : '✕')} ${m.note}${size}${tok}`;
}

function renderTaskGroups() {
  const box = $('taskGroups');
  box.innerHTML = '';
  REGISTRY.groups.forEach((g) => {
    const div = document.createElement('div');
    div.className = 'g';
    div.innerHTML = `<div class="gt"><span>${g.label}</span>
      <button data-g="${g.key}">전체/해제</button></div>`;
    const items = document.createElement('div');
    items.className = 'items';
    g.items.forEach((it) => {
      const fs = it.num_fewshot === null || it.num_fewshot === undefined
        ? '' : `${it.num_fewshot}-shot`;
      const lab = document.createElement('label');
      lab.innerHTML =
        `<input type="checkbox" class="taskchk" value="${it.key}" data-group="${g.key}">
         <span>${it.label}</span><span class="fs">${fs}</span>`;
      items.appendChild(lab);
    });
    div.appendChild(items);
    box.appendChild(div);
  });
  box.querySelectorAll('.gt button').forEach((b) => {
    b.onclick = () => {
      const chks = [...box.querySelectorAll(`.taskchk[data-group="${b.dataset.g}"]`)];
      const on = chks.some((c) => !c.checked);
      chks.forEach((c) => { c.checked = on; });
      refreshDerived();
    };
  });
  box.querySelectorAll('.taskchk').forEach((c) => { c.onchange = refreshDerived; });
}

async function loadConfig() {
  const r = await fetch('/api/config').then((x) => x.json());
  DEFAULTS = r.defaults;
  applyConfig(r.config);
  showDerived(r.derived);
}

function showDerived(d) {
  const m = d.model || {};
  $('i_resolved').textContent = d.resolved_model + (d.model_exists ? '' : '  ⚠ 없음');
  $('i_resolved').style.color = d.model_exists ? '#cbd5e1' : '#fca5a5';
  $('i_name').textContent = d.model_name || '-';
  $('i_token').textContent = d.hf_token ? '설정됨' : '없음 (gated 모델은 필요)';
  $('i_token').style.color = d.hf_token ? '#4ade80' : '#94a3b8';
  $('i_results').textContent = d.results_json;
  $('i_log').textContent = d.log_path;
  renderModelStat(d);
}

let derivedTimer = null;
function refreshDerived() {
  clearTimeout(derivedTimer);
  derivedTimer = setTimeout(async () => {
    const r = await fetch('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collectConfig()),
    }).then((x) => x.json()).catch(() => null);
    if (r && r.ok) {
      const d = await fetch('/api/config').then((x) => x.json());
      showDerived(d.derived);
    }
  }, 500);
}

/* --------------------------------------------------------------- 실행/중지 */
async function run() {
  const cfg = collectConfig();
  if (!cfg.tasks.length) { alert('평가 항목을 1개 이상 선택하세요.'); return; }
  $('btnRun').disabled = true;
  const r = await fetch('/api/run', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config: cfg, save: true }),
  }).then((x) => x.json());
  if (!r.ok) { alert('실행 실패: ' + r.error); $('btnRun').disabled = false; return; }
  resetView();
  $('logBox').textContent = r.will_download
    ? `${r.model} 를 HuggingFace 에서 내려받는 중입니다 (수 분~수십 분 소요) ...\n`
    : '평가를 시작했습니다 ...\n';
  poll();
}

async function stop() {
  if (!confirm('실행 중인 평가를 중지할까요?')) return;
  const r = await fetch('/api/stop', { method: 'POST' }).then((x) => x.json());
  if (!r.ok) alert(r.error);
}

/* ------------------------------------------------------------ 상태 렌더링 */
const STATE_TXT = { running: '실행 중', done: '완료', error: '오류', stopped: '중지됨' };

function renderStages(stages) {
  const box = $('stages');
  box.innerHTML = '';
  (stages || []).forEach((s) => {
    const d = document.createElement('div');
    d.className = 'stage ' + (s.status || 'pending');
    const mark = s.status === 'done' ? '✓' : (s.status === 'error' ? '!' : '');
    d.innerHTML = `<div class="lnk"></div><div class="circ">${mark}</div>
      <div class="nm">${s.name}</div><div class="sb">${s.sub}</div>`;
    box.appendChild(d);
  });
}

function fmt(v, digits = 2) {
  return (v === null || v === undefined || Number.isNaN(v)) ? '-' : Number(v).toFixed(digits);
}

function renderSummary(st) {
  const s = (st.results && st.results.summary) || {};
  const c = s.counts || {};
  const cards = [
    { k: '영어 core 평균', v: s.core_en, cls: 'blue', s: `${c.core_en || 0}개 벤치마크` },
    { k: '한국어 평균', v: s.korean, cls: 'green', s: `KoBEST · KMMLU (${c.korean || 0}개)` },
    { k: '생성형 평균', v: s.generative, cls: 'purple', s: `F1 · BLEU · ROUGE (${(c.generative || 0) + (c.custom || 0)}개)` },
    { k: '종합', v: s.overall, cls: 'amber', s: '전체 대표지표 평균' },
  ];
  $('summaryCards').innerHTML = cards.map((x) => `
    <div class="scard"><div class="k">${x.k}</div>
      <div class="v ${x.cls}">${x.v === null || x.v === undefined ? '–' : fmt(x.v)}</div>
      <div class="s">${x.s}</div></div>`).join('');
}

function renderBenchList(st) {
  const bms = (st.results && st.results.benchmarks) || [];
  const box = $('benchList');
  if (!bms.length) {
    box.innerHTML = '<div class="empty">결과가 없습니다. 평가를 실행하세요.</div>';
    return;
  }
  box.innerHTML = bms.map((b) => {
    const v = b.primary_value;
    const has = v !== null && v !== undefined;
    const w = has ? Math.max(0, Math.min(100, v)) : 0;
    const cls = GROUP_COLOR[b.group] || 'b';
    const state = b.status === 'error' ? 'error' : (has ? '' : 'pending');
    const val = b.status === 'error' ? '실패'
      : (b.status === 'running' ? '평가 중 …' : (has ? fmt(v) : '-'));
    return `<div class="brow ${state}">
      <div class="bt"><span>${b.label}<span class="mt">${b.primary_label || ''}${
        b.num_fewshot !== null && b.num_fewshot !== undefined ? ' · ' + b.num_fewshot + '-shot' : ''
      }</span></span><span class="vv">${val}</span></div>
      <div class="line"><div class="bar"><div class="fill ${cls}" style="width:${w}%"></div></div></div>
    </div>`;
  }).join('');
}

function renderGenTable(st) {
  const s = (st.results && st.results.summary) || {};
  const rows = s.generative_table || [];
  const tb = $('genTable').querySelector('tbody');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="7" class="empty">SQuADv2 / TruthfulQA-gen / 커스텀 평가를 선택하면 표시됩니다.</td></tr>';
    return;
  }
  const pick = (m, keys) => {
    for (const k of keys) if (m[k] !== undefined) return fmt(m[k]);
    return '-';
  };
  tb.innerHTML = rows.map((r) => `<tr>
    <td>${r.label}</td>
    <td class="num">${pick(r.metrics, ['f1', 'best_f1'])}</td>
    <td class="num">${pick(r.metrics, ['em', 'exact', 'exact_match'])}</td>
    <td class="num">${pick(r.metrics, ['bleu', 'bleu_max'])}</td>
    <td class="num">${pick(r.metrics, ['rouge1', 'rouge1_max'])}</td>
    <td class="num">${pick(r.metrics, ['rouge2', 'rouge2_max'])}</td>
    <td class="num">${pick(r.metrics, ['rougeL', 'rougeL_max'])}</td>
  </tr>`).join('');
}

function renderDetailTable(st) {
  const bms = (st.results && st.results.benchmarks) || [];
  const tb = $('detailTable').querySelector('tbody');
  const rows = [];
  bms.forEach((b) => {
    const mets = b.metrics && b.metrics.length ? b.metrics : [null];
    mets.forEach((m, i) => {
      rows.push(`<tr>
        <td>${i === 0 ? b.label : ''}</td>
        <td>${i === 0 ? (b.task || 'custom') : ''}</td>
        <td class="num">${i === 0 ? (b.num_fewshot ?? '-') : ''}</td>
        <td>${m ? m.label : '-'}</td>
        <td class="num">${m ? m.text : '-'}</td>
        <td class="num">${m && m.stderr !== null && m.stderr !== undefined ? '±' + fmt(m.stderr) : '-'}</td>
        <td class="num">${i === 0 ? (b.n_samples ?? '-') : ''}</td>
        <td class="num">${i === 0 ? (b.elapsed ?? '-') : ''}</td>
        <td>${i === 0 ? `<span class="pill ${b.status}">${b.status}</span>` : ''}</td>
      </tr>`);
    });
  });
  tb.innerHTML = rows.length ? rows.join('') : '<tr><td colspan="9" class="empty">-</td></tr>';
}

/* ------------------------------------------------------------ 레이더 차트 */
function drawRadar(st) {
  const cv = $('radar');
  const ctx = cv.getContext('2d');
  const data = ((st.results && st.results.summary) || {}).radar || [];
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  if (data.length < 3) {
    ctx.fillStyle = '#6b7280';
    ctx.font = '13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('카테고리 3개 이상 결과가 필요합니다', W / 2, H / 2);
    $('radarLegend').innerHTML = '';
    return;
  }
  const cx = W / 2, cy = H / 2 + 6, R = Math.min(W, H) / 2 - 62;
  const n = data.length;
  const ang = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;

  // 그리드
  for (let ring = 1; ring <= 4; ring++) {
    const r = (R * ring) / 4;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = cx + r * Math.cos(ang(i)), y = cy + r * Math.sin(ang(i));
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = ring === 4 ? '#39404d' : '#262b34';
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  ctx.strokeStyle = '#262b34';
  for (let i = 0; i < n; i++) {
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + R * Math.cos(ang(i)), cy + R * Math.sin(ang(i)));
    ctx.stroke();
  }

  // 데이터 폴리곤 (0~100 스케일)
  ctx.beginPath();
  data.forEach((d, i) => {
    const r = (R * Math.max(0, Math.min(100, d.value))) / 100;
    const x = cx + r * Math.cos(ang(i)), y = cy + r * Math.sin(ang(i));
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = 'rgba(59,130,246,.22)';
  ctx.fill();
  ctx.strokeStyle = '#60a5fa';
  ctx.lineWidth = 2;
  ctx.stroke();
  data.forEach((d, i) => {
    const r = (R * Math.max(0, Math.min(100, d.value))) / 100;
    ctx.beginPath();
    ctx.arc(cx + r * Math.cos(ang(i)), cy + r * Math.sin(ang(i)), 3, 0, 7);
    ctx.fillStyle = '#4ade80';
    ctx.fill();
  });

  // 라벨
  ctx.fillStyle = '#9aa2af';
  ctx.font = '11px sans-serif';
  data.forEach((d, i) => {
    const a = ang(i);
    const x = cx + (R + 26) * Math.cos(a), y = cy + (R + 22) * Math.sin(a);
    ctx.textAlign = Math.abs(Math.cos(a)) < 0.25 ? 'center' : (Math.cos(a) > 0 ? 'left' : 'right');
    ctx.textBaseline = 'middle';
    ctx.fillText(d.category, x, y);
  });
  $('radarLegend').innerHTML = data
    .map((d) => `<span>${d.category} <b style="color:#cbd5e1">${fmt(d.value)}</b></span>`).join('');
}

/* ------------------------------------------------------------ 초기 상태 */
const PIPELINE_DEFAULT =
  '파이프라인 · prepare → download → load → english → korean → generative → score';

/** 진행 상황 / 결과 / 로그 영역을 0 · 공란으로 되돌린다. */
function resetView() {
  $('stateDot').className = 'dot';
  $('stateBadge').className = 'badge';
  $('stateBadge').textContent = '대기';
  $('pipelineText').textContent = PIPELINE_DEFAULT;
  $('stages').innerHTML = '';
  $('overallFill').style.width = '0%';
  $('overallPct').textContent = '0%';
  $('currentFill').style.width = '0%';
  $('currentPct').textContent = '0%';
  $('currentLabel').textContent = '현재';
  $('runMeta').textContent = '대기 중 — 설정을 확인하고 [실행]을 누르세요.';
  $('warnBox').hidden = true;
  $('warnBox').innerHTML = '';
  renderSummary({});
  renderBenchList({});
  renderGenTable({});
  renderDetailTable({});
  drawRadar({});
  $('logBox').textContent = '(로그 없음)';
}

/* ------------------------------------------------------------------ 폴링 */
function renderStatus(res) {
  const st = res.status || {};
  const running = res.running;
  if (res.fresh) {          // 서버 시작 후 아직 실행한 적이 없다 — 빈 화면 유지
    resetView();
    $('btnRun').disabled = false;
    $('btnStop').disabled = true;
    return false;
  }
  const state = running ? 'running' : (st.state || 'idle');

  $('stateDot').className = 'dot ' + (state === 'running' ? 'running'
    : state === 'done' ? 'done' : state === 'error' ? 'error' : '');
  $('stateBadge').className = 'badge ' + (state === 'running' ? 'running'
    : state === 'done' ? 'done' : state === 'error' ? 'error' : '');
  $('stateBadge').textContent = STATE_TXT[state] || '대기';
  $('btnRun').disabled = running;
  $('btnStop').disabled = !running;

  if (st.stages) {
    renderStages(st.stages);
    $('pipelineText').textContent = '파이프라인 · ' +
      st.stages.map((s) => s.name.toLowerCase()).join(' → ');
  }

  const p = st.progress || {};
  const op = p.overall_pct || 0, cp = p.current_pct || 0;
  $('overallFill').style.width = op + '%';
  $('overallPct').textContent = fmt(op, 0) + '%';
  $('currentFill').style.width = cp + '%';
  $('currentPct').textContent = fmt(cp, 0) + '%';
  $('currentLabel').textContent = p.current_label
    ? `${p.current_label}${p.current_desc ? ' · ' + p.current_desc : ''}` : '현재';

  const m = st.model || {}, c = st.config || {};
  if (st.state) {
    const done = p.tasks_done || 0, tot = p.tasks_total || 0;
    $('runMeta').innerHTML =
      `모델 <b>${m.name || '-'}</b> · dtype ${m.dtype || c.dtype || '-'}` +
      (m.params ? ` · ${(m.params / 1e9).toFixed(2)}B params` : '') +
      `<br>진행 ${done}/${tot} 벤치마크 · 경과 ${fmt(st.elapsed, 0)}s` +
      ` · limit ${c.limit ?? '전체'} · batch ${c.batch_size ?? '-'}` +
      ` · few-shot ${c.num_fewshot ?? '권장값'}` +
      ` · chat_template ${c.apply_chat_template ? 'on' : 'off'}` +
      (st.error ? `<br><span style="color:#fca5a5">오류: ${st.error}</span>` : '');
  }

  const warns = st.warnings || [];
  $('warnBox').hidden = !warns.length;
  if (warns.length) $('warnBox').innerHTML = warns.map((w) => '⚠ ' + w).join('<br>');

  renderSummary(st);
  renderBenchList(st);
  renderGenTable(st);
  renderDetailTable(st);
  drawRadar(st);

  const box = $('logBox');
  const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
  box.textContent = res.log || '(로그 없음)';
  if ($('autoScroll').checked && atBottom) box.scrollTop = box.scrollHeight;
  return running;
}

let wasRunning = false;
async function poll() {
  try {
    const res = await fetch('/api/status').then((x) => x.json());
    const running = renderStatus(res);
    if (wasRunning && !running) {
      // 실행이 끝나면 캐시 상태(다운로드 결과)를 다시 읽는다.
      loadModels().then(() => loadConfig());
    }
    wasRunning = running;
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, running ? 1200 : 6000);
  } catch (e) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, 8000);
  }
}

/* GPU 상태는 <details> 가 펼쳐져 있을 때만 폴링한다.
   (닫혀 있으면 서버에 요청을 보내지 않는다 — 액세스 로그/부하 절감) */
let gpuTimer = null;
async function pollGpu() {
  clearTimeout(gpuTimer);
  const open = $('gpuDetails') && $('gpuDetails').open;
  if (open) {
    try {
      const g = await fetch('/api/gpus').then((x) => x.json());
      $('gpuInfo').textContent = Array.isArray(g)
        ? g.map((x) => `GPU${x.index} ${x.name} · ${x.mem_used}/${x.mem_total} MiB · ${x.util}%`).join('\n')
        : 'nvidia-smi 사용 불가';
    } catch (e) { /* ignore */ }
  }
  gpuTimer = setTimeout(pollGpu, open ? 5000 : 20000);
}

/* ------------------------------------------------------------------ 초기화 */
async function loadModels() {
  MODELS = await fetch('/api/models').then((x) => x.json())
    .catch(() => ({ models: [], hf_token: false }));
  renderModelPresets();
  syncPreset();
}

async function init() {
  REGISTRY = await fetch('/api/registry').then((x) => x.json());
  renderTaskGroups();
  await loadModels();
  await loadConfig();

  $('btnRun').onclick = run;
  $('btnStop').onclick = stop;
  $('btnSave').onclick = async () => {
    const r = await fetch('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collectConfig()),
    }).then((x) => x.json());
    alert(r.ok ? '설정을 저장했습니다: ' + r.path : '저장 실패');
    loadConfig();
  };
  $('btnReset').onclick = () => {
    if (!confirm('기본값으로 복원할까요? (저장은 별도로 눌러야 적용)')) return;
    applyConfig(DEFAULTS);
    refreshDerived();
  };
  $('btnYamlReload').onclick = loadYaml;
  $('btnYamlSave').onclick = async () => {
    const r = await fetch('/api/config/raw', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: $('rawYaml').value }),
    }).then((x) => x.json());
    const el = $('yamlMsg');
    el.className = 'msg ' + (r.ok ? 'ok' : 'err');
    el.textContent = r.ok ? '저장했습니다.' : r.error;
    if (r.ok) loadConfig();
  };
  document.querySelectorAll('[data-preset]').forEach((b) => {
    b.onclick = () => {
      const p = b.dataset.preset;
      document.querySelectorAll('.taskchk').forEach((c) => {
        if (p === 'all') c.checked = true;
        else if (p === 'none') c.checked = false;
        else if (p === 'default') c.checked = REGISTRY.default_selected.includes(c.value);
        else c.checked = (c.dataset.group === p);
      });
      refreshDerived();
    };
  });
  FIELDS.forEach((f) => { const el = $(f); if (el) el.onchange = refreshDerived; });
  CHECKS.forEach((f) => { $(f).onchange = refreshDerived; });
  $('model_preset').onchange = onPresetChange;
  $('model_path').onchange = () => { syncPreset(); refreshDerived(); };
  $('gpuDetails').ontoggle = () => { if ($('gpuDetails').open) pollGpu(); };

  loadYaml();
  resetView();
  poll();
  pollGpu();
}

async function loadYaml() {
  const r = await fetch('/api/config/raw').then((x) => x.json());
  $('rawYaml').value = r.text || '';
}

init();
