import { useEffect, useState } from 'react';

import { Loading } from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';

import { fetchExpertImageBlob } from '@src/apis/llm/evaluation';

import BboxCropStrip from './BboxCropStrip';
import BboxLayer from './BboxLayer';
import { buildCrops, cropsOmitted } from './bboxCrop';
import { extractShipBoxes } from './sdsAis';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 멀티모달 — VLM 샘플 이미지 렌더. URL 이미지(image_url)는 직접, NFS 서버 이미지(image_served)는
// jf 헤더 인증 blob 으로 받아 objectURL 로(직접 <img src> GET 은 헤더 미탑재라 인증 실패).
// 언마운트/샘플 변경 시 objectURL revoke(누수 방지), 실패 시 플레이스홀더. (blob 패턴 불변 — 인증 경로 유지)
//   확대: 채점 시 선박/해상 장면의 세부(타선 위치·등화)를 봐야 하는데 인라인 크기로는 판독이
//   어려워, 클릭하면 같은 objectURL 을 뷰포트 크기로 띄우는 라이트박스를 연다(재요청 없음).
//   SDS 샘플은 AIS 표(csv_rows)에 타선 bbox 가 같이 오므로, 어느 점이 어느 배인지 좌표를 눈으로
//   대조하지 않도록 이미지 위에 박스를 그리고 배마다 확대 크롭을 따로 붙인다(전문가 피드백).
const CROP_COLORS = [
  '#ffd23f',
  '#ff77c8',
  '#4dd0e1',
  '#ff9e4a',
  '#b388ff',
  '#7ed957',
  '#ff6b6b',
  '#5b9dff',
];

const ExpertSampleImage = ({ modelId, jobId, sample, t }) => {
  const [src, setSrc] = useState(null);
  const [err, setErr] = useState(false);
  const [zoomed, setZoomed] = useState(false);
  // 박스 좌표가 원본 픽셀이라 % 로 환산하려면 원본 크기가 필요하다 — 로드 시점에만 알 수 있다.
  const [nat, setNat] = useState(null);

  useEffect(() => {
    setNat(null); // 샘플이 바뀌면 이전 이미지 크기로 박스를 그리지 않는다
    if (sample.image_url) {
      setSrc(sample.image_url);
      return undefined;
    }
    if (!sample.image_served || modelId == null || !jobId) return undefined;
    let active = true;
    let objectUrl = null;
    setSrc(null);
    setErr(false);
    (async () => {
      try {
        const blob = await fetchExpertImageBlob(modelId, jobId, sample.idx);
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      } catch {
        if (active) setErr(true);
      }
    })();
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [modelId, jobId, sample.idx, sample.image_url, sample.image_served]);

  // 이전/다음 네비로 샘플이 바뀌면 확대를 닫는다(직전 샘플 이미지가 떠 있는 채로 남지 않도록).
  useEffect(() => setZoomed(false), [sample.idx]);

  // 확대 중에는 Esc 로 닫고 배경 스크롤을 잠근다. 정리에서 반드시 복구 — 복구를 빼먹으면
  // 라이트박스를 닫은 뒤에도 페이지 스크롤이 잠긴 채 남는다(ExpertInferenceModal 선례).
  useEffect(() => {
    if (!zoomed) return undefined;
    const onKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      event.stopImmediatePropagation(); // 상위 모달/프레임의 Esc 핸들러 동시 발화 차단
      setZoomed(false);
    };
    document.addEventListener('keydown', onKeyDown, true);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = 'auto';
    };
  }, [zoomed]);

  // graceful(D5): 이미지 소스 없으면 영역 자체를 생략.
  if (!sample.image_url && !sample.image_served) return null;
  if (err) {
    return (
      <div className={cx('img-status')}>
        <EmptyBox
          text='evaluation.expert.imageError'
          isBox
          isRed
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }
  if (!src)
    return (
      <div className={cx('img-status')}>
        <Loading />
        <span>{t('evaluation.project.loading')}</span>
      </div>
    );
  // alt 는 파일명이 있으면 그것을(무엇을 보고 있는지 가장 구체적), 없으면 번역된 일반
  // 설명으로 떨어진다 — 하드코딩 영문 'sample' 은 한국어 로케일에서도 그대로 읽혔다.
  const alt = sample.image || t('evaluation.expert.imageAlt');
  // 박스·크롭은 AIS 표(bbox 열)와 원본 크기가 둘 다 있을 때만 — 일반 이미지 샘플은 종전 그대로.
  const boxes = extractShipBoxes(sample.csv_rows);
  const crops =
    nat && boxes.length > 0
      ? buildCrops(boxes, nat.width, nat.height, CROP_COLORS)
      : [];
  const regions = crops.map((crop) => ({
    key: crop.key,
    index: crop.index,
    color: crop.color,
    x: crop.originX,
    y: crop.originY,
    w: crop.viewW,
    h: crop.viewH,
  }));
  // 삼항 — `boxes.length &&` 로 두면 0 이 그대로 JSX 로 새어 화면에 "0" 이 찍힌다.
  const overlay =
    nat && boxes.length > 0 ? (
      <BboxLayer
        boxes={boxes}
        width={nat.width}
        height={nat.height}
        regions={regions}
      />
    ) : null;
  const onLoad = (event) =>
    setNat({
      width: event.target.naturalWidth,
      height: event.target.naturalHeight,
    });

  return (
    <>
      {/* div+onClick 이 아니라 button — Tab 으로 도달 못 하면 키보드 사용자는 확대 자체가 불가. */}
      <button
        type='button'
        className={cx('img-button')}
        onClick={() => setZoomed(true)}
        title={t('evaluation.expert.imageZoom')}
        aria-label={t('evaluation.expert.imageZoom')}
      >
        {/* 오버레이는 % 좌표라 이미지 표시 영역에 정확히 겹쳐야 한다 — 이미지에 딱 맞는 래퍼. */}
        <span className={cx('img-frame')}>
          <img className={cx('img')} src={src} alt={alt} onLoad={onLoad} />
          {overlay}
        </span>
      </button>

      <BboxCropStrip
        src={src}
        crops={crops}
        natWidth={nat?.width}
        natHeight={nat?.height}
        omitted={cropsOmitted(boxes)}
        t={t}
      />

      {zoomed && (
        <div
          className={cx('lightbox')}
          role='dialog'
          aria-modal='true'
          aria-label={t('evaluation.expert.imageZoom')}
          onClick={() => setZoomed(false)}
        >
          {/* 이미지 본체 클릭은 닫지 않는다 — 배경(오버레이)만 닫기 영역. */}
          <span
            className={cx('lightbox-frame')}
            onClick={(event) => event.stopPropagation()}
          >
            <img
              className={cx('lightbox-img')}
              src={src}
              alt={alt}
              onLoad={onLoad}
            />
            {overlay}
          </span>
          {/* aria-modal 을 선언한 이상 열릴 때 포커스가 안으로 들어와야 한다(안 그러면 뒤쪽
              콘텐츠로 Tab 이 새고, Esc 로 닫을 수 있다는 것도 드러나지 않는다). 완전한 포커스
              트랩까지는 두지 않는다 — 닫기 버튼 하나뿐인 오버레이라 과설계. */}
          <button
            type='button'
            className={cx('lightbox-close')}
            onClick={() => setZoomed(false)}
            aria-label={t('evaluation.expert.imageZoomClose')}
            autoFocus
          >
            ×
          </button>
        </div>
      )}
    </>
  );
};

export default ExpertSampleImage;
