// 플레이스홀더 이미지 명세.
//
// 실제 데이터가 붙기 전까지 화면이 비어 보이지 않도록 쓰는 가짜 장면이다.
// SVG 문자열을 innerHTML 로 꽂지 않고 도형 명세만 내보내고, 그리는 것은
// components 의 <Frame> 이 JSX 로 한다 — 마크업 주입 경로를 만들지 않기 위해서.
//
// 실제 이미지가 연결되면 이 파일은 통째로 지워도 된다.

// 플랫폼이 싣는 본문 폰트. 목업의 Source Code Pro 는 여기 없다.
const MONO = 'SpoqaM, sans-serif';

const t = (x, y, str, opt = {}) => ({
  t: 'text', x, y, s: str, fs: opt.fs || 9, fill: opt.fill || '#121619',
  anchor: opt.anchor, bold: opt.bold, family: opt.family || MONO, opacity: opt.opacity,
});
const r = (x, y, w, h, fill, opt = {}) => ({
  t: 'rect', x, y, w, h, fill, stroke: opt.stroke, dash: opt.dash, opacity: opt.opacity,
});
const ln = (x1, y1, x2, y2, stroke) => ({ t: 'line', x1, y1, x2, y2, stroke });
const c = (cx, cy, rad, fill, opt = {}) => ({ t: 'circle', cx, cy, r: rad, fill, opacity: opt.opacity });
const p = (d, opt = {}) => ({
  t: 'path', d, fill: opt.fill || 'none', stroke: opt.stroke,
  sw: opt.sw || 1, opacity: opt.opacity,
});

export const VIEWBOX = '0 0 320 200';

// ── 범용 파이프라인 플레이스홀더 4종 ────────────────────────────────────────
// 0 문서(거래 명세서) · 1 차트 · 2 합성 장면 · 3 지형
export const SHOTS = [
  [
    r(0, 0, 320, 200, '#ffffff'),
    r(18, 14, 284, 172, '#fbfcff', { stroke: '#dbdbdb' }),
    t(30, 34, '거래 명세서 No. 2026-0417', { fs: 10 }),
    ln(30, 42, 290, 42, '#042659'),
    t(36, 58, '품목', { fill: '#747474' }),
    t(196, 58, '단가', { fill: '#747474' }),
    t(250, 58, '금액', { fill: '#747474' }),
    ln(30, 64, 290, 64, '#f0f0f0'),
    t(36, 80, '연결부 A'),
    t(196, 80, '4,200'),
    t(250, 80, '50,400'),
    ln(30, 86, 290, 86, '#f0f0f0'),
    t(36, 102, '밸브 C'),
    t(196, 102, '18,500'),
    t(250, 102, '55,500'),
    ln(30, 108, 290, 108, '#f0f0f0'),
    t(196, 152, '합계', { fill: '#747474' }),
    t(250, 152, '133,500', { fs: 10, bold: true }),
    // 정답이 있는 칸을 점선으로 표시 — 검수 화면에서 어디를 봐야 하는지 힌트.
    r(244, 141, 52, 15, 'none', { stroke: '#fa4e57', dash: '2 2' }),
  ],
  [
    r(0, 0, 320, 200, '#ffffff'),
    t(14, 20, '분기별 처리량 (천 건)', { fill: '#747474' }),
    ln(34, 170, 306, 170, '#dbdbdb'),
    ln(34, 34, 34, 170, '#dbdbdb'),
    r(52, 112, 34, 58, '#2d76f8'),
    t(69, 107, '58', { anchor: 'middle' }),
    t(69, 184, 'Q1', { anchor: 'middle', fill: '#747474' }),
    r(116, 86, 34, 84, '#2d76f8'),
    t(133, 81, '84', { anchor: 'middle' }),
    t(133, 184, 'Q2', { anchor: 'middle', fill: '#747474' }),
    r(180, 99, 34, 71, '#34b2e3'),
    t(197, 94, '71', { anchor: 'middle' }),
    t(197, 184, 'Q3', { anchor: 'middle', fill: '#747474' }),
    r(244, 58, 34, 112, '#0f6cc7'),
    t(261, 53, '112', { anchor: 'middle' }),
    t(261, 184, 'Q4', { anchor: 'middle', fill: '#747474' }),
  ],
  [
    r(0, 0, 320, 200, '#f5f7fb'),
    r(0, 140, 320, 60, '#dee9ff'),
    c(54, 132, 17, '#2d76f8'),
    c(104, 126, 13, '#00c775'),
    c(150, 134, 19, '#ffab31'),
    c(196, 128, 14, '#2d76f8'),
    c(244, 131, 16, '#00c775'),
    c(282, 127, 12, '#2d76f8'),
    r(70, 96, 22, 22, '#747474'),
    r(130, 88, 26, 26, '#747474'),
    r(210, 92, 20, 20, '#747474'),
  ],
  [
    r(0, 0, 320, 200, '#dee9ff'),
    p('M0 132 L74 78 L128 122 L188 62 L258 118 L320 84 L320 200 L0 200Z', { fill: '#93baff' }),
    p('M0 158 L96 118 L172 156 L262 122 L320 150 L320 200 L0 200Z', { fill: '#164abe' }),
    c(252, 46, 17, '#ffffff'),
    r(128, 150, 20, 30, '#042659'),
    r(154, 158, 15, 22, '#042659'),
  ],
];

// ── 해양(브리지 카메라) 플레이스홀더 ────────────────────────────────────────
// 두 선박이 프레임마다 서로 접근한다 — 조우 상황이 진행되는 것을 보여주기 위해서.
// [자선측 x, y, 크기, 상대선 x, y, 크기]
const SEQ = [
  [128, 96, 30, 214, 118, 20],
  [150, 98, 32, 196, 116, 19],
  [172, 100, 34, 178, 114, 18],
  [196, 102, 37, 160, 112, 17],
  [220, 104, 40, 142, 110, 16],
  [244, 106, 43, 124, 108, 15],
];

/** 선체 — 사다리꼴 선체 + 선교 + 마스트. */
function hull(x, y, w, fill) {
  return [
    p(`M${x} ${y} l${w} 0 l-${Math.round(w * 0.16)} ${Math.round(w * 0.17)} l-${Math.round(w * 0.68)} 0 z`, { fill }),
    r(x + Math.round(w * 0.26), y - Math.round(w * 0.2), Math.round(w * 0.3), Math.round(w * 0.2), fill),
    r(x + Math.round(w * 0.38), y - Math.round(w * 0.34), Math.round(w * 0.06), Math.round(w * 0.14), fill),
  ];
}

/** AIS 로 계산된 영역 좌표 — 기하 변형이 걸리면 이게 어긋나는 것이 문제의 핵심이다. */
function bbox(x, y, w, h, label) {
  return [
    r(x, y, w, h, 'none', { stroke: '#00c775' }),
    r(x, y - 11, label.length * 5.4 + 8, 11, '#00c775'),
    t(x + 4, y - 3, label, { fs: 8, fill: '#ffffff' }),
  ];
}

export function seaFrame(i) {
  const q = SEQ[i % SEQ.length];
  return [
    r(0, 0, 320, 200, '#c8dbfd'),
    r(0, 0, 320, 104, '#dee9ff'),
    r(0, 104, 320, 96, '#93baff'),
    r(0, 104, 320, 3, '#164abe', { opacity: 0.35 }),
    c(264, 40, 13, '#ffffff', { opacity: 0.85 }),
    p('M0 150 q40 -5 80 0 t80 0 t80 0 t80 0', { stroke: '#164abe', opacity: 0.25 }),
    p('M0 172 q40 -5 80 0 t80 0 t80 0 t80 0', { stroke: '#164abe', opacity: 0.2 }),
    ...hull(q[0], q[1], q[2], '#042659'),
    ...bbox(q[0] - 4, q[1] - Math.round(q[2] * 0.4), q[2] + 10, Math.round(q[2] * 0.62), 's_014'),
    ...hull(q[3], q[4], q[5], '#164abe'),
    ...bbox(q[3] - 3, q[4] - Math.round(q[5] * 0.4), q[5] + 8, Math.round(q[5] * 0.62), 's_027'),
    r(8, 8, 128, 15, 'rgba(4,38,89,0.72)'),
    t(13, 19, `08:14:0${i % 10} HDG 045 12.4kn`, { fill: '#ffffff' }),
  ];
}
