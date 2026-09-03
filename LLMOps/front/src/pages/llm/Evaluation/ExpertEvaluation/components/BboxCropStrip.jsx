import BboxLayer from './BboxLayer';
import { CROP_H, CROP_W, CROP_ZOOM_LABEL_MIN } from './bboxCrop';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 확대 크롭 패널 — 기하 계산(확대율·크롭 원점)은 bboxCrop 에 있고 여기는 표시만 한다.
const BboxCropStrip = ({ src, crops, natWidth, natHeight, omitted, t }) => {
  if (!crops.length) return null;
  return (
    <div className={cx('crop-strip')}>
      {/* 제목 줄은 두지 않는다 — 패널마다 캡션(선박ID·확대율)이 이미 무엇인지 말한다. */}
      <div className={cx('crop-list')}>
        {crops.map((crop) => (
          <div className={cx('crop')} key={crop.key}>
            <div
              className={cx('crop-view')}
              style={{
                width: CROP_W,
                height: CROP_H,
                borderColor: crop.color,
              }}
            >
              {/* 확대는 transform 이 아니라 레이아웃 크기로 건다 — transform 은 오버레이의 ID
                  이름표 글자까지 같이 확대해 패널을 덮는다. */}
              <div
                className={cx('crop-inner')}
                style={{
                  left: -crop.originX * crop.zoom,
                  top: -crop.originY * crop.zoom,
                  width: natWidth * crop.zoom,
                  height: natHeight * crop.zoom,
                }}
              >
                {/* 확대일 때만 최근접 보간(픽셀이 그대로 커진다) — 축소에 걸면 계단만 생긴다. */}
                <img
                  className={cx('crop-img')}
                  src={src}
                  alt=''
                  style={{
                    imageRendering: crop.zoom > 1 ? 'pixelated' : 'auto',
                  }}
                />
                <BboxLayer
                  boxes={[crop]}
                  width={natWidth}
                  height={natHeight}
                />
              </div>
            </div>
            <div className={cx('crop-caption')}>
              {t(
                crop.zoom >= CROP_ZOOM_LABEL_MIN
                  ? 'evaluation.expert.bboxCropCaption'
                  : 'evaluation.expert.bboxCropCaptionPlain',
                {
                  index: crop.index,
                  shipId: crop.shipId || '-',
                  zoom: crop.zoom.toFixed(1),
                },
              )}
            </div>
          </div>
        ))}
      </div>
      {omitted > 0 && (
        <span className={cx('crop-omitted')}>
          {t('evaluation.expert.bboxCropMore', { count: omitted })}
        </span>
      )}
    </div>
  );
};

export default BboxCropStrip;
