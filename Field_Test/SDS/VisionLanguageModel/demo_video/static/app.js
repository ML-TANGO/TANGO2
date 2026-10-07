// demo_video/static/app.js — 영상 기반 SDS-VLM 데모 화면
"use strict";

const $ = (id) => document.getElementById(id);
const video = $("video");
const state = { index: null, scn: null, frames: null, results: null, resultKeys: [],
                cpaCurve: [], frame: 1, analyzing: false,
                mode: "pre",                                   // "pre" 미리 계산 결과, "rt" 실시간 추론
                rt: { runs: [], current: null, abort: null } }; // 실시간 추론 기록 (현재 시나리오)

// ── 데이터 ────────────────────────────────────────────────────────────────
async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function shipsAt(frame) {
  const f = state.frames;
  const rows = f.ships[frame - f.first_frame] || [];
  const k = Object.fromEntries(f.ship_fields.map((n, i) => [n, i]));
  return rows.map((r) => ({ id: r[k.ship_id], own: r[k.my_ship] === 1, lat: r[k.latitude], lon: r[k.longitude],
                            knot: r[k.knot], heading: r[k.heading], cpa: r[k.cpa], tcpa: r[k.tcpa], length: r[k.length] }));
}

// 자선 기준 북(N)·동(E) 방향 거리 (해리). 수 해리 범위라 평면 근사로 충분하다.
function relNM(own, s) {
  const n = (s.lat - own.lat) * 60;
  const e = (s.lon - own.lon) * 60 * Math.cos((own.lat * Math.PI) / 180);
  return { n, e, d: Math.hypot(n, e) };
}

function riskClass(s) {
  if (s.own || s.tcpa < 0) return "";
  if (s.cpa < 0.5) return "risk-high";
  if (s.cpa < 1.0) return "risk-mid";
  return "";
}

// ── 시나리오 ──────────────────────────────────────────────────────────────
async function loadScenario(s) {
  const token = (state.loadToken = (state.loadToken || 0) + 1);
  document.querySelectorAll(".scn").forEach((b) => b.classList.toggle("on", b.dataset.id === s.id));
  const frames = await getJSON(`/data/${s.id}/frames.json`);
  let results = null;
  try {
    results = await getJSON(`/data/${s.id}/results.json`);
  } catch {
    results = null;
  }
  if (token !== state.loadToken) return;     // 더 나중에 누른 시나리오가 있으면 버린다
  rtReset();
  state.scn = s;
  state.frames = frames;
  state.results = results;
  $("ov-body").dataset.k = "";
  state.resultKeys = state.results ? Object.keys(state.results.frames).map(Number).sort((a, b) => a - b) : [];
  // 프레임별 최근접 위험 선박의 CPA (아직 지나가지 않은 선박 중 최소)
  state.cpaCurve = state.frames.ships.map((_, i) => {
    const vals = shipsAt(state.frames.first_frame + i).filter((x) => !x.own && x.tcpa >= 0).map((x) => x.cpa);
    return vals.length ? Math.min(...vals) : null;
  });
  video.src = `/data/${s.id}/video.mp4`;
  video.load();
  $("live").hidden = state.mode !== "rt";
  if (state.mode === "rt") $("live-text").textContent = rtSummary();
  updateFoot();
  render(state.frames.first_frame);
  if (state.mode === "rt") video.play().catch(() => {});   // 실시간 추론 모드에서는 바로 재생해 분석을 이어 간다
}

function updateFoot() {
  const r = state.results;
  const every = r ? `${(r.every / state.frames.fps).toFixed(0)}초 간격으로 ${r.device}에서 미리 분석` : "미리 분석된 결과 없음";
  $("foot-data").textContent =
    `데이터: SDS 시뮬레이터 ${state.index.session} 수집 세션 (학습 데이터와 별도) · ${every}`;
}

// ── 프레임 동기화 ─────────────────────────────────────────────────────────
function frameFromTime(t) {
  const f = state.frames;
  return f.first_frame + Math.min(f.frame_count - 1, Math.max(0, Math.floor(t * f.fps + 1e-3)));
}
function timeOfFrame(frame) {
  return (frame - state.frames.first_frame + 0.5) / state.frames.fps;
}

function tick() {
  if (state.frames) {
    const fr = frameFromTime(video.currentTime);
    if (fr !== state.frame) render(fr);
  }
  if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(tick);
  else requestAnimationFrame(tick);
}

// ── 화면 갱신 ─────────────────────────────────────────────────────────────
function render(frame) {
  state.frame = frame;
  const f = state.frames;
  const t = (frame - f.first_frame) / f.fps;
  $("clock").textContent = `${t.toFixed(1)} / ${(f.frame_count / f.fps).toFixed(1)}초`;
  renderOverlay(frame);
  renderInput(frame);
  renderShips(frame);
  drawTimeline();
}

function gridFrameAt(frame) {
  const f = state.frames;
  const step = f.grid.length > 1 ? f.grid[1] - f.grid[0] : 1;
  return f.first_frame + Math.floor((frame - f.first_frame) / step) * step;
}

function renderInput(frame) {
  // 실시간 추론 중에는 모델이 지금 보고 있는 장면(분석 중이거나 마지막으로 분석한 장면)을 보여 준다
  const rtFrame = state.mode === "rt" && (state.rt.current || state.rt.runs.at(-1))?.frame;
  const g = rtFrame || gridFrameAt(frame);
  const id = state.scn.id;
  const src = `/data/${id}/inputs/f${String(g).padStart(6, "0")}.png`;
  if ($("in-img").dataset.src !== src) {
    $("in-img").src = src;
    $("in-img").dataset.src = src;
    $("ais-text").textContent = state.frames.ais[g] || "";
  }
  $("in-frame").textContent = `${((g - state.frames.first_frame) / state.frames.fps).toFixed(1)}초 장면`;
}

function escapeHTML(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// 청중이 핵심을 빨리 찾도록 조항, 조종 동작, 위험 표현만 강조한다
function highlight(text) {
  return escapeHTML(text)
    .replace(/(COLREG\s*)?제\s?\d+(?:\s?[·,및]\s?\d+)*\s?조/g, (m) => `<mark class="rule">${m}</mark>`)
    .replace(/(우현|좌현)\s?\d*\s?도?\s?변침(?:과)?|감속|증속|속력\s?유지|침로\s?유지|충돌\s?위험|피항\s?의무|피항선|유지선/g,
             (m) => `<mark>${m}</mark>`);
}

function splitOutput(text) {
  const parts = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  if (parts.length < 2) return [["", text]];
  return [["상황", parts[0]], ["조언", parts.slice(1).join(" ")]];
}

function outputHTML(text, block) {
  return splitOutput(text)
    .map(([lbl, p]) => {
      const head = lbl ? (block ? `<span class="lbl">${lbl}</span>` : `<b>${lbl}</b> `) : "";
      return block ? `<p>${head}${highlight(p)}</p>` : `${head}${highlight(p)}`;
    }).join(block ? "" : "\n\n");
}

// 실시간 분석 결과는 그 장면(분석 격자 프레임)에 머무는 동안 오버레이에 우선 표시한다
function renderLiveOverlay() {
  const L = state.live;
  const body = $("ov-body");
  body.dataset.k = "live";
  $("ov-time").textContent = `${((L.frame - state.frames.first_frame) / state.frames.fps).toFixed(1)}초 장면 · 실시간 분석`;
  body.innerHTML = L.text ? outputHTML(L.text, true) + (L.done ? "" : `<span class="cursor"></span>`)
                          : `<p class="empty">이미지와 AIS를 읽는 중…</p>`;
}

// 스트리밍 중에도 사용자가 다른 시나리오나 장면으로 옮겼으면 그 화면을 덮지 않는다
function refreshLive() {
  const L = state.live;
  if (L && state.scn && L.scenario === state.scn.id && gridFrameAt(state.frame) === L.frame) renderLiveOverlay();
}

const secOf = (frame) => (frame - state.frames.first_frame) / state.frames.fps;

// 실시간 추론 모드: 마지막으로 끝난 결과를 보여 주고, 진행 중인 분석은 아래 줄에 경과 시간으로 표시한다
function renderRtOverlay() {
  const body = $("ov-body"), foot = $("ov-foot");
  const last = state.rt.runs.at(-1), cur = state.rt.current;
  let key, head, html;
  if (last) {
    key = `rt-done-${state.rt.runs.length}`;
    const lag = (last.endFrame - last.frame) / state.frames.fps;
    // 결과가 나오기 전에 영상이 끝났거나 멈췄으면 영상 진행량은 추론 시간을 대표하지 못한다
    const lagText = last.interrupted ? "결과가 나오기 전에 영상이 멈추거나 끝났음"
                                     : `결과가 나왔을 때 영상은 ${lag.toFixed(1)}초 앞서 있었음`;
    // 청중이 기다린 시간은 브라우저에서 잰 시간(요청~마지막 글자)이다. 서버에서 잰 시간은 괄호로 함께 둔다
    head = `${secOf(last.frame).toFixed(1)}초 장면을 실시간 추론한 결과 · <b>추론 ${last.client_s.toFixed(1)}초</b>` +
           ` (서버 ${last.wall_s.toFixed(1)}초) · ${lagText}`;
    html = outputHTML(last.text, true);
  } else if (cur && cur.text) {
    key = `rt-cur-${cur.text.length}`;
    head = `${secOf(cur.frame).toFixed(1)}초 장면을 실시간 추론하는 중`;
    html = outputHTML(cur.text, true) + `<span class="cursor"></span>`;
  } else {
    key = cur ? "rt-wait" : "rt-idle";
    head = "실시간 추론";
    html = cur ? `<p class="empty">${secOf(cur.frame).toFixed(1)}초 장면의 이미지와 AIS를 모델에 넣는 중…</p>`
               : `<p class="empty">재생하면 Jetson Orin이 영상을 보면서 장면을 하나씩 실시간으로 분석합니다. 미리 계산된 결과는 쓰지 않습니다.</p>`;
  }
  if (body.dataset.k !== key) {
    body.dataset.k = key;
    $("ov-time").innerHTML = head;
    body.innerHTML = html;
  }
  foot.hidden = !cur && !state.rt.error;
  if (cur) {
    const el = (performance.now() - cur.t0) / 1000;
    foot.innerHTML = `<span class="pulse"></span>${secOf(cur.frame).toFixed(1)}초 장면 분석 중 · ` +
                     `${el.toFixed(1)}초 경과 · ${cur.tokens}토큰 생성 · 그사이 영상은 계속 재생됩니다`;
  } else if (state.rt.error) {
    foot.textContent = state.rt.error;
  }
}

function renderOverlay(frame) {
  if (state.mode === "rt") return renderRtOverlay();
  $("ov-foot").hidden = true;
  if (state.live && state.live.scenario === state.scn.id && gridFrameAt(frame) === state.live.frame) {
    if ($("ov-body").dataset.k !== "live") renderLiveOverlay();
    return;
  }
  const keys = state.resultKeys;
  let k = null;
  for (const x of keys) { if (x <= frame) k = x; else break; }
  const body = $("ov-body");
  if (k === null) {
    $("ov-time").textContent = "";
    body.innerHTML = keys.length
      ? `<p class="empty">첫 분석 시점을 기다리는 중입니다</p>`
      : `<p class="empty">미리 분석된 결과가 없습니다. 오른쪽 ‘현재 장면 분석하기’를 눌러 보세요.</p>`;
    body.dataset.k = "";
    return;
  }
  if (body.dataset.k === String(k)) return;
  body.dataset.k = String(k);
  const r = state.results.frames[k];
  $("ov-time").textContent = `${((k - state.frames.first_frame) / state.frames.fps).toFixed(1)}초 장면을 분석한 결과`;
  body.innerHTML = outputHTML(r.text, true);
}

function renderShips(frame) {
  const ships = shipsAt(frame);
  const own = ships.find((s) => s.own);
  if (!own) return;
  const targets = ships.filter((s) => !s.own).map((s) => ({ ...s, rel: relNM(own, s) }))
    .sort((a, b) => a.rel.d - b.rel.d);
  $("own-spd").textContent = `${own.knot.toFixed(1)} kn`;
  $("own-hdg").textContent = `${own.heading.toFixed(0)}°`;
  $("n-targets").textContent = `${targets.length}척`;
  const rows = [`<tr class="own"><td>자선</td><td>–</td><td>${own.knot.toFixed(1)}kn</td><td>–</td><td>–</td></tr>`];
  for (const s of targets) {
    const rc = riskClass(s);
    const tc = s.tcpa < 0 ? "지남" : `${Math.round(s.tcpa)}초`;
    rows.push(`<tr><td>선박 ${s.id} <span class="muted">${Math.round(s.length)}m</span></td>` +
      `<td>${s.rel.d.toFixed(2)}NM</td><td>${s.knot.toFixed(1)}kn</td>` +
      `<td class="${rc}">${s.cpa.toFixed(2)}NM</td><td>${tc}</td></tr>`);
  }
  $("ship-rows").innerHTML = rows.join("");
  drawRadar(own, targets);
}

// ── 레이더 (자선 중심, 북쪽 위) ───────────────────────────────────────────
function setupCanvas(c, cssW, cssH) {
  const dpr = window.devicePixelRatio || 1;
  if (c.width !== Math.round(cssW * dpr) || c.height !== Math.round(cssH * dpr)) {
    c.width = Math.round(cssW * dpr);
    c.height = Math.round(cssH * dpr);
  }
  const g = c.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cssW, cssH);
  return g;
}

function niceRange(d) {
  for (const r of [0.5, 1, 2, 3, 4, 6, 8, 12, 16]) if (d <= r) return r;
  return Math.ceil(d / 4) * 4;
}

function drawShipMark(g, x, y, headingDeg, size, color) {
  g.save();
  g.translate(x, y);
  g.rotate((headingDeg * Math.PI) / 180);
  g.beginPath();
  g.moveTo(0, -size);
  g.lineTo(size * 0.6, size * 0.8);
  g.lineTo(-size * 0.6, size * 0.8);
  g.closePath();
  g.fillStyle = color;
  g.fill();
  g.restore();
}

function drawRadar(own, targets) {
  const c = $("radar");
  const W = c.clientWidth || 230;
  const g = setupCanvas(c, W, W);
  const cx = W / 2, cy = W / 2, R = W / 2 - 18;
  const range = niceRange(Math.max(0.5, ...targets.map((t) => t.rel.d)) * 1.1);
  g.strokeStyle = "#e2e6ea";
  g.fillStyle = "#64707d";
  g.font = "11px sans-serif";
  g.textAlign = "left";
  for (let i = 1; i <= 2; i++) {
    g.beginPath();
    g.arc(cx, cy, (R * i) / 2, 0, Math.PI * 2);
    g.stroke();
    g.fillText(`${((range * i) / 2).toFixed(range < 2 ? 1 : 0)}NM`, cx + 4, cy - (R * i) / 2 + 12);
  }
  g.beginPath(); g.moveTo(cx, cy - R); g.lineTo(cx, cy + R); g.moveTo(cx - R, cy); g.lineTo(cx + R, cy); g.stroke();
  g.textAlign = "center";
  g.fillText("N", cx, 12);
  const scale = R / range;
  // 침로 벡터: 6분 동안 이동할 거리
  const vec = (knot, hdg) => { const d = (knot * 0.1) * scale; const a = (hdg * Math.PI) / 180; return [Math.sin(a) * d, -Math.cos(a) * d]; };
  for (const t of targets) {
    const x = cx + t.rel.e * scale, y = cy - t.rel.n * scale;
    const color = t.tcpa >= 0 && t.cpa < 0.5 ? "#d6453d" : t.tcpa >= 0 && t.cpa < 1.0 ? "#d98a00" : "#5b6b7b";
    const [vx, vy] = vec(t.knot, t.heading);
    g.strokeStyle = color; g.beginPath(); g.moveTo(x, y); g.lineTo(x + vx, y + vy); g.stroke();
    drawShipMark(g, x, y, t.heading, 7, color);
    g.fillStyle = color; g.fillText(`${t.id}`, x, y + 18);
  }
  const [ox, oy] = vec(own.knot, own.heading);
  g.strokeStyle = "#0b6bcb"; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + ox, cy + oy); g.stroke();
  drawShipMark(g, cx, cy, own.heading, 8, "#0b6bcb");
  g.fillStyle = "#0b6bcb"; g.fillText("자선", cx, cy + 20);
}

// ── 타임라인 (최근접 CPA 곡선, 분석 시점, 재생 위치) ─────────────────────
function drawTimeline() {
  const c = $("timeline");
  const W = c.clientWidth, H = 64;
  const g = setupCanvas(c, W, H);
  const f = state.frames, n = f.frame_count;
  const vals = state.cpaCurve.filter((v) => v !== null);
  const maxC = Math.max(1, ...vals) * 1.1;
  const X = (i) => (i / Math.max(1, n - 1)) * (W - 2) + 1;
  const Y = (v) => H - 14 - (v / maxC) * (H - 22);
  // 0.5NM 주의선
  g.setLineDash([4, 4]); g.strokeStyle = "#d6453d"; g.beginPath(); g.moveTo(0, Y(0.5)); g.lineTo(W, Y(0.5)); g.stroke(); g.setLineDash([]);
  // CPA 곡선
  g.strokeStyle = "#0b6bcb"; g.lineWidth = 2; g.beginPath();
  let started = false;
  state.cpaCurve.forEach((v, i) => {
    if (v === null) { started = false; return; }
    if (!started) { g.moveTo(X(i), Y(v)); started = true; } else g.lineTo(X(i), Y(v));
  });
  g.stroke(); g.lineWidth = 1;
  if (state.mode === "rt") {
    // 실시간 추론: 분석한 장면(점)에서 결과가 나온 시점까지 막대. 막대 길이가 곧 지연이다
    // 연속된 분석이 하나의 막대로 붙어 보이지 않도록 두 줄에 번갈아 그리고 시작점을 진하게 찍는다
    const spans = state.rt.runs.map((r) => [r.frame, r.endFrame, 1]);
    if (state.rt.current) spans.push([state.rt.current.frame, state.frame, 0.45]);
    spans.forEach(([a, b, alpha], i) => {
      const y = i % 2 ? H - 16 : H - 8;
      const xa = X(a - f.first_frame);
      g.globalAlpha = alpha;
      g.fillStyle = "#e08a00";
      g.fillRect(xa, y, Math.max(2, X(b - f.first_frame) - xa), 5);
      g.fillStyle = "#17202a";
      g.beginPath(); g.arc(xa, y + 2.5, 3.5, 0, Math.PI * 2); g.fill();
    });
    g.globalAlpha = 1;
  } else {
    // 미리 계산된 분석 시점
    g.fillStyle = "#17202a";
    for (const k of state.resultKeys) { g.beginPath(); g.arc(X(k - f.first_frame), H - 5, 3.5, 0, Math.PI * 2); g.fill(); }
  }
  // 재생 위치
  const px = X(state.frame - f.first_frame);
  g.strokeStyle = "#17202a"; g.beginPath(); g.moveTo(px, 0); g.lineTo(px, H); g.stroke();
}

$("timeline").addEventListener("click", (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
  video.currentTime = ratio * (state.frames.frame_count / state.frames.fps - 0.01);
});

// ── 재생 조작 ─────────────────────────────────────────────────────────────
$("play").addEventListener("click", () => (video.paused ? video.play() : video.pause()));
video.addEventListener("play", () => ($("play").textContent = "❚❚"));
video.addEventListener("pause", () => ($("play").textContent = "▶"));
video.addEventListener("seeked", () => state.frames && render(frameFromTime(video.currentTime)));
document.querySelectorAll("[data-rate]").forEach((b) => b.addEventListener("click", () => {
  video.playbackRate = Number(b.dataset.rate);
  document.querySelectorAll("[data-rate]").forEach((x) => x.classList.toggle("on", x === b));
}));
$("show-ais").addEventListener("click", () => {
  const p = $("ais-text");
  p.hidden = !p.hidden;
  $("show-ais").textContent = p.hidden ? "AIS 입력 문장 보기" : "AIS 입력 문장 닫기";
});
window.addEventListener("resize", () => state.frames && render(state.frame));

// ── 분석 요청 (수동 분석과 실시간 추론이 함께 쓴다) ───────────────────────
// /api/analyze 의 SSE 를 읽으며 onToken(누적 텍스트) 을 부르고, 끝나면 결과를 돌려준다.
async function streamAnalysis(scenario, frame, onToken, signal) {
  const t0 = performance.now();
  const r = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ scenario, frame }), signal });
  if (!r.ok) {
    const err = new Error((await r.json().catch(() => ({}))).error || r.statusText);
    err.status = r.status;
    throw err;
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "", raw = "", first = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) throw new Error("모델 서버의 응답이 중간에 끊겼습니다");
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 2);
      if (!line.startsWith("data:")) continue;
      const ev = JSON.parse(line.slice(5));
      if (ev.error) throw new Error(ev.error);
      if (ev.content) {
        if (first === null) first = (performance.now() - t0) / 1000;
        raw += ev.content;
        // Qwen3 의 (빈) 사고 구간은 보이지 않게 한다
        onToken(raw.includes("</think>") ? raw.split("</think>").pop().trim() : (raw.includes("<think>") ? "" : raw));
      }
      if (ev.stop) {
        return { text: raw.split("</think>").pop().trim(), timings: ev.timings || {},
                 first_token_s: ev.first_token_s ?? first, wall_s: ev.wall_s ?? (performance.now() - t0) / 1000 };
      }
    }
  }
}

function showMetrics(res) {
  $("m-first").textContent = res.first_token_s != null ? `${res.first_token_s.toFixed(1)}초` : "–";
  $("m-speed").textContent = res.timings?.predicted_per_second != null ? `${res.timings.predicted_per_second.toFixed(1)} 토큰/초` : "–";
  $("m-total").textContent = `${res.wall_s.toFixed(1)}초`;
}

// ── 수동 분석 (미리 계산 모드): 멈추고 그 장면을 분석한다 ────────────────
$("analyze").addEventListener("click", async () => {
  if (state.analyzing || !state.frames || state.mode !== "pre") return;
  video.pause();
  const g = gridFrameAt(state.frame);
  video.currentTime = timeOfFrame(g);
  state.analyzing = true;
  const btn = $("analyze");
  btn.disabled = true;
  btn.textContent = "분석 중…";
  $("live").hidden = false;
  const out = $("live-text");
  out.textContent = "이미지와 AIS를 모델에 넣는 중입니다…";
  ["m-first", "m-speed", "m-total"].forEach((id) => ($(id).textContent = "–"));
  state.live = { scenario: state.scn.id, frame: g, text: "", done: false };
  refreshLive();
  const t0 = performance.now();
  const timer = setInterval(() => ($("m-total").textContent = `${((performance.now() - t0) / 1000).toFixed(1)}초`), 100);
  try {
    const res = await streamAnalysis(state.scn.id, g, (shown) => {
      if (!state.live.text) $("m-first").textContent = `${((performance.now() - t0) / 1000).toFixed(1)}초`;
      out.textContent = "생성 중입니다. 결과는 영상 위에 나타납니다.";
      state.live.text = shown;
      refreshLive();
    });
    clearInterval(timer);
    showMetrics(res);
    out.textContent = `완료 · 생성 ${res.timings.predicted_n ?? "–"}토큰. 결과는 영상 위에 표시되어 있습니다.`;
    state.live.text = res.text;
    state.live.done = true;
    refreshLive();
  } catch (e) {
    out.textContent = `분석하지 못했습니다: ${e.message}`;
    state.live = null;
    $("ov-body").dataset.k = "";
    renderOverlay(state.frame);
  } finally {
    clearInterval(timer);
    state.analyzing = false;
    btn.disabled = false;
    btn.textContent = "현재 장면 분석하기";
  }
});

// ── 실시간 추론 모드: 재생 중 쉬지 않고 현재 장면을 분석한다 ─────────────
function rtReset() {
  if (state.rt.current) state.analyzing = false;   // 중단한 분석이 잡고 있던 표시를 푼다
  state.rt.abort?.abort();
  state.rt = { runs: [], current: null, abort: null, error: null };
}

function rtSummary() {
  const runs = state.rt.runs;
  if (!runs.length) return "재생 중에 장면을 하나씩 분석합니다.";
  const avg = runs.reduce((a, r) => a + r.client_s, 0) / runs.length;
  return `이번 시나리오에서 ${runs.length}개 장면을 분석했습니다 · 장면당 평균 ${avg.toFixed(1)}초`;
}

async function rtLoop() {
  if (state.mode !== "rt" || state.rt.current || state.analyzing || !state.frames || video.paused || video.ended) return;
  const scenario = state.scn.id;
  const run = { frame: gridFrameAt(state.frame), startFrame: state.frame, text: "", tokens: 0, t0: performance.now() };
  const abort = new AbortController();
  state.rt.current = run;
  state.rt.abort = abort;
  state.rt.error = null;
  state.analyzing = true;
  $("live-text").textContent = rtSummary();
  ["m-first", "m-speed", "m-total"].forEach((id) => ($(id).textContent = "–"));
  renderInput(state.frame);
  renderRtOverlay();
  const timer = setInterval(() => {
    $("m-total").textContent = `${((performance.now() - run.t0) / 1000).toFixed(1)}초`;
    if (state.mode === "rt" && state.scn.id === scenario) { renderRtOverlay(); drawTimeline(); }
  }, 200);
  let retry = 0;
  try {
    const res = await streamAnalysis(scenario, run.frame, (shown) => {
      if (!run.tokens) $("m-first").textContent = `${((performance.now() - run.t0) / 1000).toFixed(1)}초`;
      run.tokens += 1;
      run.text = shown;
    }, abort.signal);
    if (state.scn.id !== scenario || state.rt.current !== run) return;   // 그사이 시나리오나 모드가 바뀜
    Object.assign(run, res, { endFrame: state.frame, client_s: (performance.now() - run.t0) / 1000,
                              interrupted: run.interrupted || video.ended || video.paused });
    state.rt.runs.push(run);
    showMetrics({ ...res, wall_s: run.client_s });
  } catch (e) {
    if (e.name === "AbortError" || state.rt.current !== run) return;
    if (e.status === 409) {                    // 다른 사람이 분석 중이면 잠시 뒤 다시 시도
      state.rt.error = "다른 분석이 끝나기를 기다리는 중입니다";
      retry = 1500;
    } else {
      state.rt.error = `분석하지 못했습니다: ${e.message}`;
      retry = 3000;
    }
  } finally {
    clearInterval(timer);
    if (state.rt.current === run) {
      state.rt.current = null;
      state.rt.abort = null;
      state.analyzing = false;
      $("live-text").textContent = rtSummary();
      if (state.mode === "rt" && state.scn.id === scenario) { renderInput(state.frame); renderRtOverlay(); drawTimeline(); }
      setTimeout(rtLoop, retry);               // 끝나는 즉시 지금 장면으로 다음 분석
    }
  }
}

function setMode(mode) {
  if (state.mode === mode) return;
  state.mode = mode;
  document.querySelectorAll("[data-mode]").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
  const rt = mode === "rt";
  $("lg-pre").hidden = rt;
  $("lg-rt").hidden = !rt;
  $("analyze").hidden = rt;
  $("live-title").textContent = rt ? "실시간 추론" : "지금 이 장면 분석";
  rtReset();
  state.analyzing = false;
  state.live = null;
  $("live").hidden = !rt;
  $("live-text").textContent = rt ? rtSummary() : "";
  ["m-first", "m-speed", "m-total"].forEach((id) => ($(id).textContent = "–"));
  $("ov-body").dataset.k = "";
  $("in-img").dataset.src = "";
  render(state.frame);
  if (rt) {
    if (video.ended) video.currentTime = 0;
    video.play();
  }
}

document.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
video.addEventListener("play", () => setTimeout(rtLoop, 0));
video.addEventListener("pause", () => { if (state.rt.current) state.rt.current.interrupted = true; });

// ── 모델 서버 상태 ────────────────────────────────────────────────────────
async function pollStatus() {
  const el = $("status");
  try {
    const s = await getJSON("/api/status");
    const device = state.results?.device || "Jetson AGX Orin";
    el.className = `status ${s.ready ? (s.busy ? "busy" : "ok") : "down"}`;
    el.querySelector(".label").textContent = s.ready
      ? `${device} · ${s.busy ? "분석 중" : "모델 준비됨"}`
      : "모델 서버에 연결되지 않음";
  } catch {
    el.className = "status down";
    el.querySelector(".label").textContent = "데모 서버에 연결되지 않음";
  }
}

// ── 시작 ──────────────────────────────────────────────────────────────────
(async function init() {
  state.index = await getJSON("/data/scenarios.json");
  const nav = $("scenarios");
  for (const s of state.index.scenarios) {
    const b = document.createElement("button");
    b.className = "scn";
    b.dataset.id = s.id;
    b.innerHTML = `<b>${s.title}</b><small>${s.collision_course ? '<span class="badge">충돌 코스</span> · ' : ""}` +
                  `주변 선박 ${s.num_targets}척 · ${s.duration_sec.toFixed(0)}초</small>`;
    b.addEventListener("click", () => loadScenario(s));
    nav.appendChild(b);
  }
  await loadScenario(state.index.scenarios[0]);
  tick();
  pollStatus();
  setInterval(pollStatus, 5000);
})();
