import { useMemo } from 'react';

import { RADAR_INK, TURN_COLOR } from './logickorResult';

// LogicKor 영역 레이더(1턴 vs 2턴). 소스 모듈 웹 콘솔의 drawRadar 를 그대로 옮겼다 —
// 지오메트리(320x300, 중심 160/150, 반경 95, 4겹 격자)와 라벨 규칙이 동일하다.
// 차트 라이브러리를 쓰지 않는 이유: front 에 레이더 선례가 없고(0곳), 이 페이지는 지금
// 차트 번들을 전혀 안 싣는다. llm/ 페이지에는 인라인 SVG 선례가 이미 있다(NodeCanvas 등).
const W = 320;
const H = 300;
const CX = 160;
const CY = 150;
const R = 95;
const RINGS = 4;
const LABEL_GAP = 16;
const MIN_AXES = 3; // 축이 2개 이하면 다각형이 안 되므로 그리지 않는다.

// #rrggbb → rgba(). 채움색을 선색과 따로 관리하지 않으려고 알파만 얹는다.
const withAlpha = (hex, alpha) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};

const FILL_ALPHA = 0.18;

const LogicKorRadar = ({ categories, scaleMax = 10 }) => {
  const geom = useMemo(() => {
    const n = categories?.length || 0;
    if (n < MIN_AXES) return null;

    const max = Number(scaleMax) > 0 ? Number(scaleMax) : 10;
    const angle = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const point = (i, radius) => [
      CX + radius * Math.cos(angle(i)),
      CY + radius * Math.sin(angle(i)),
    ];
    const polygon = (radiusAt) =>
      categories
        .map((_, i) => point(i, radiusAt(i)).join(','))
        .join(' ');

    // 점수 → 반경. 척도를 넘는 값이 격자 밖으로 튀지 않게 클램프한다.
    const radiusFor = (value) => {
      const ratio = Number(value) / max;
      return R * Math.max(0, Math.min(1, Number.isFinite(ratio) ? ratio : 0));
    };

    return {
      rings: Array.from({ length: RINGS }, (_, ring) =>
        polygon(() => (R * (ring + 1)) / RINGS),
      ),
      spokes: categories.map((_, i) => point(i, R)),
      labels: categories.map((c, i) => {
        const [x, y] = point(i, R + LABEL_GAP);
        return {
          x,
          y,
          // 괄호 안 영문 표기는 라벨이 서로 겹쳐 잘리므로 떼고 한글만 쓴다(소스와 동일).
          text: String(c.category || '').replace(/\(.*\)/, ''),
          anchor:
            Math.abs(x - CX) < 8 ? 'middle' : x < CX ? 'end' : 'start',
        };
      }),
      single: polygon((i) => radiusFor(categories[i].single)),
      multi: polygon((i) => radiusFor(categories[i].multi)),
    };
  }, [categories, scaleMax]);

  if (!geom) return null;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role='img'>
      {geom.rings.map((points, i) => (
        <polygon
          key={`ring-${i}`}
          points={points}
          fill='none'
          stroke={RADAR_INK.grid}
        />
      ))}
      {geom.spokes.map(([x, y], i) => (
        <line
          key={`spoke-${i}`}
          x1={CX}
          y1={CY}
          x2={x}
          y2={y}
          stroke={RADAR_INK.grid}
        />
      ))}
      {geom.labels.map((label) => (
        <text
          key={label.text}
          x={label.x}
          y={label.y}
          fill={RADAR_INK.label}
          fontSize='10'
          textAnchor={label.anchor}
          dominantBaseline='middle'
        >
          {label.text}
        </text>
      ))}
      <polygon
        points={geom.single}
        fill={withAlpha(TURN_COLOR.single, FILL_ALPHA)}
        stroke={TURN_COLOR.single}
        strokeWidth='2'
      />
      <polygon
        points={geom.multi}
        fill={withAlpha(TURN_COLOR.multi, FILL_ALPHA)}
        stroke={TURN_COLOR.multi}
        strokeWidth='2'
      />
    </svg>
  );
};

export default LogicKorRadar;
