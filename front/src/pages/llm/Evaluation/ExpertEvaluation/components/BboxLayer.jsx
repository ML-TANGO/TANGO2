import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 이미지 위 바운딩박스 레이어. 부모가 "원본 이미지 전체"를 덮는다는 전제로 % 좌표만 쓰기 때문에
// 인라인·라이트박스·확대 크롭 어디에 얹어도 같은 컴포넌트가 그대로 맞는다.
//   SVG viewBox 로 그리지 않는 이유: 배율에 따라 ID 이름표 글자까지 같이 줄거나 늘어나
//   축소된 원본에서는 못 읽고 3배 크롭에서는 화면을 덮는다. HTML+% 는 글자만 고정 px 로 남는다.
// 색·두께·이름표 위치는 SDS 데모(_draw_bboxes)와 같은 규약 — 초록 박스 + 박스 위쪽 ID 이름표.
const LABEL_INSIDE_RATIO = 0.05; // 박스가 상단에 붙으면 이름표를 위에 두면 잘린다 → 안쪽으로

const pct = (value, total) => `${(value / total) * 100}%`;

// regions: 확대 크롭이 잘라 간 영역 표시(패널의 테두리 색·번호와 짝) — 어느 배가 어느 패널인지.
const BboxLayer = ({ boxes, width, height, regions = [] }) => {
  if (!width || !height) return null;
  return (
    <span className={cx('bbox-layer')} aria-hidden='true'>
      {regions.map((region) => (
        <span
          key={`region-${region.key}`}
          className={cx('bbox-region')}
          style={{
            left: pct(region.x, width),
            top: pct(region.y, height),
            width: pct(region.w, width),
            height: pct(region.h, height),
            borderColor: region.color,
          }}
        >
          <span
            className={cx('bbox-region-index', {
              'bbox-region-index--inside': region.y / height < LABEL_INSIDE_RATIO,
            })}
            style={{ backgroundColor: region.color }}
          >
            {region.index}
          </span>
        </span>
      ))}
      {boxes.map((box) => (
        <span
          key={box.key}
          className={cx('bbox')}
          style={{
            left: pct(box.x, width),
            top: pct(box.y, height),
            width: pct(box.w, width),
            height: pct(box.h, height),
          }}
        >
          <span
            className={cx('bbox-label', {
              'bbox-label--inside': box.y / height < LABEL_INSIDE_RATIO,
            })}
          >
            {`ID:${box.shipId || '?'}`}
          </span>
        </span>
      ))}
    </span>
  );
};

export default BboxLayer;
