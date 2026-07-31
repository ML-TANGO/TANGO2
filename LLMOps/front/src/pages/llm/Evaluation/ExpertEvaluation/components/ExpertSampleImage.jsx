import { useEffect, useState } from 'react';

import { Loading } from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';

import { fetchExpertImageBlob } from '@src/apis/llm/evaluation';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 멀티모달 — VLM 샘플 이미지 렌더. URL 이미지(image_url)는 직접, NFS 서버 이미지(image_served)는
// jf 헤더 인증 blob 으로 받아 objectURL 로(직접 <img src> GET 은 헤더 미탑재라 인증 실패).
// 언마운트/샘플 변경 시 objectURL revoke(누수 방지), 실패 시 플레이스홀더. (blob 패턴 불변 — 인증 경로 유지)
const ExpertSampleImage = ({ modelId, jobId, sample, t }) => {
  const [src, setSrc] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
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
  return <img className={cx('img')} src={src} alt={sample.image || 'sample'} />;
};

export default ExpertSampleImage;
