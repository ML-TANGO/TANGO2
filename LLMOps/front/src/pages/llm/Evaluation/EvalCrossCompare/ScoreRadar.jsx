import classNames from 'classnames/bind';
import style from './EvalCrossCompare.module.scss';

const cx = classNames.bind(style);

// 카테고리별 평균 레이더 — 요약 카드(buildScorecards)의 보조 그림이다. 숫자는 카드에 이미
// 있으므로 이 그림은 "어느 축에서 벌어지나"를 한눈에 보이는 것만 맡는다(스크린리더에는
// aria-label 로 요약만 준다 — 값을 한 번 더 읽히면 카드와 중복이다).
//
// 축은 0~100 고정이다 — 평균에 넣는 지표가 전부 0~100 정답률 계열이라(buildScorecards)
// 척도를 데이터에 맞춰 늘이면 작은 차이가 크게 보인다.
// 같은 모델의 두 번째 이후 평가 대상(다른 체크포인트)은 같은 색에 점선으로 그린다 — 색은
// 모델을, 선 모양은 체크포인트를 가리킨다(행렬 열 머리와 같은 약속).

const SIZE = 300;
const CENTER = SIZE / 2;
const RADIUS = 104;
const RINGS = [25, 50, 75, 100];

const point = (index, count, value) => {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
  const r = (Math.max(0, Math.min(125, value)) / 100) * RADIUS;
  return [CENTER + r * Math.cos(angle), CENTER + r * Math.sin(angle)];
};

/**
 * @param {{
 *   axes: { id: string, label: string }[],
 *   series: { key: string, label: string, colorIndex: number, dashed: boolean,
 *             values: Record<string, number | null> }[],
 *   title: string,
 * }} props
 */
const ScoreRadar = ({ axes, series, title }) => {
  const count = axes.length;
  const ring = (value) =>
    axes.map((_, i) => point(i, count, value).join(',')).join(' ');

  return (
    <figure className={cx('radar')}>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className={cx('radar-svg')}
        role='img'
        aria-label={title}
      >
        {RINGS.map((value) => (
          <polygon
            key={value}
            points={ring(value)}
            className={cx('radar-ring')}
          />
        ))}
        {axes.map((axis, i) => {
          const [x, y] = point(i, count, 100);
          const [lx, ly] = point(i, count, 120);
          return (
            <g key={axis.id}>
              <line
                x1={CENTER}
                y1={CENTER}
                x2={x}
                y2={y}
                className={cx('radar-axis')}
              />
              <text
                x={lx}
                y={ly}
                className={cx('radar-label')}
                textAnchor={
                  Math.abs(lx - CENTER) < 4
                    ? 'middle'
                    : lx > CENTER
                      ? 'start'
                      : 'end'
                }
                dominantBaseline='middle'
              >
                {axis.label}
              </text>
            </g>
          );
        })}
        {series.map((s) => (
          <polygon
            key={s.key}
            points={axes
              .map((axis, i) =>
                point(i, count, Math.min(100, s.values[axis.id] ?? 0)).join(
                  ',',
                ),
              )
              .join(' ')}
            className={cx(
              'radar-series',
              `rs-${s.colorIndex}`,
              s.dashed && 'dashed',
            )}
          />
        ))}
      </svg>
      <figcaption className={cx('radar-legend')}>
        {series.map((s) => (
          <span key={s.key} className={cx('radar-legend-item')}>
            <i
              className={cx(
                'radar-swatch',
                `rs-${s.colorIndex}`,
                s.dashed && 'dashed',
              )}
            />
            {s.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
};

export default ScoreRadar;
