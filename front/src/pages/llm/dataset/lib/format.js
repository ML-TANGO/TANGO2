// 데이터 파이프라인 화면 공용 계산.
//
// 서버(apps/llm_data_pipeline/src/data_pipeline/constants.py)와 같은 규칙을 화면에서도
// 즉시 보여주기 위한 클라이언트 사본이다. 값이 갈리면 서버가 정본이며,
// 실제 API 연결 후에는 GET /data-pipelines/meta 로 받아 덮어쓴다.

export const fmt = (n) => Number(n || 0).toLocaleString('en-US');

// ── 4축 심사 ────────────────────────────────────────────────────────────────
export const AXES = [
  { k: 'align', label: '이미지 정합도', short: '정합' },
  { k: 'imgdep', label: '이미지 의존도', short: '의존' },
  { k: 'answer', label: '답변 가능성', short: '답변' },
  { k: 'unique', label: '정답 유일성', short: '유일' },
];

export const THRESHOLDS = { align: 0.75, imgdep: 0.8, answer: 0.8, unique: 0.7 };

// 통과율 정상 범위. 낮으면 생성이 나쁘고, 높으면 게이트가 헐거워 사실상 거르지 못한다.
export const PASS_RANGE = [40, 85];

/**
 * 게이트 상태 — 통과 / 경계 / 미달.
 *
 * '경계'를 따로 두는 이유: 임계값을 겨우 넘긴 것과 여유 있게 넘긴 것은 다르다.
 * 임계값을 조금만 올려도 떨어질 레코드를 미리 보여준다.
 */
export function gateState(value, threshold) {
  if (value < threshold) return { key: 'fail', label: '미달', tone: 'fail', hex: '#d91a0c' };
  if (value < threshold + 0.06) return { key: 'warn', label: '경계', tone: 'warn', hex: '#b35500' };
  return { key: 'pass', label: '통과', tone: 'pass', hex: '#00c775' };
}

export function isPassRateOut(rate) {
  const [lo, hi] = PASS_RANGE;
  return rate > hi || rate < lo;
}

// ── 구성 · 분할 ─────────────────────────────────────────────────────────────
/**
 * 가중치를 실제 건수로 바꾼다.
 *
 * 내림만 하면 합이 풀보다 모자란다. 남은 잔여분을 가중치가 가장 큰 유형에 몰아
 * 합계가 항상 풀과 정확히 일치하게 만든다 — 화면에 보이는 숫자의 합이 안 맞으면
 * 사용자는 어느 쪽을 믿어야 할지 알 수 없다.
 */
export function allocate(mix, weights, pool) {
  if (!mix || !mix.length) return { counts: {}, sum: 0 };
  const sum = mix.reduce((acc, m) => acc + (weights[m.k] || 0), 0) || 1;
  const biggest = mix.reduce((a, b) => ((weights[b.k] || 0) > (weights[a.k] || 0) ? b : a), mix[0]);

  const counts = {};
  let used = 0;
  mix.forEach((m) => {
    if (m === biggest) return;
    const n = Math.floor((pool * (weights[m.k] || 0)) / sum);
    counts[m.k] = n;
    used += n;
  });
  counts[biggest.k] = Math.max(0, pool - used);
  return { counts, sum };
}

/** 선택한 구성의 건수 · 이미지 토큰 · 텍스트 토큰 합계. */
export function tokenTotals(mix, counts) {
  return mix.reduce(
    (acc, m) => {
      const n = counts[m.k] || 0;
      return { recs: acc.recs + n, img: acc.img + n * m.img, txt: acc.txt + n * m.txt };
    },
    { recs: 0, img: 0, txt: 0 },
  );
}

/** 직전 버전 대비 증감 — 없으면 null(첫 버전). */
export function delta(prev, cur, key, unit = '') {
  if (!prev) return null;
  const d = (cur[key] || 0) - (prev[key] || 0);
  if (!d) return null;
  return { txt: `${d > 0 ? '+' : ''}${Math.round(d * 100) / 100}${unit}`, up: d > 0 };
}

// ── 유형별 판정 ─────────────────────────────────────────────────────────────
export const CAP_COLOR = {
  captioning: '#34b2e3',
  general_vqa: '#2d76f8',
  ocr_document: '#0f6cc7',
  chart_table: '#ffab31',
  counting: '#fa4e57',
  spatial_3d: '#c1c1c1',
  refusal: '#1e5bc5',
};

export const FLAG_TONE = {
  충분: 'pass',
  '생성 부족': 'warn',
  '데이터 부족': 'warn',
  '데이터 없음': 'fail',
};
