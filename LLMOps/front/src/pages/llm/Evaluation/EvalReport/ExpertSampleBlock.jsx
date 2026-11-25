import { useLayoutEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { parseExpertSample, sensorTable } from './expertSample';

import classNames from 'classnames/bind';
import style from './EvalReport.module.scss';

const cx = classNames.bind(style);

// 전문가 샘플 1건의 이미지 + 센서 데이터 표. 인쇄본은 이 DOM 을 그대로 옮기므로 이미지는
// 화면에 보일 때가 아니라 바로 받는다(보관은 리포트가 한다 — createSampleImages).
const ExpertSampleBlock = ({ text, images }) => {
  const { t } = useTranslation();
  const sample = useMemo(() => parseExpertSample(text), [text]);
  const [src, setSrc] = useState(null);
  const [failed, setFailed] = useState(false);

  // 첫 그림 전에 요청해야 PDF 버튼이 이미지 수를 모른 채 잠깐 풀리지 않는다.
  useLayoutEffect(() => {
    if (!sample?.image) return undefined;
    let alive = true;
    images.load(sample).then(
      (url) => alive && setSrc(url),
      () => alive && setFailed(true),
    );
    return () => {
      alive = false;
    };
  }, [sample, images]);

  if (!sample) return null;
  const table = sensorTable(t, sample.rows);
  return (
    <figure className={cx('sample')}>
      {sample.image && (
        <div className={cx('sample-image', { 'sample-image--pending': !src })}>
          {src && (
            <img src={src} alt={sample.name || t('evaluation.expert.imageAlt')} />
          )}
          {!src &&
            t(
              failed
                ? 'evaluation.expert.imageError'
                : 'evaluation.project.loading',
            )}
        </div>
      )}
      {!sample.image && sample.name && (
        <p>
          <strong>{t('evaluation.report.image')}</strong> {sample.name}
        </p>
      )}
      {table && (
        <>
          <p>
            <strong>{t('evaluation.report.sensorData')}</strong>
          </p>
          <table>
            <thead>
              <tr>
                {table.head.map((cell, i) => (
                  <th key={i}>{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.body.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, i) => (
                    <td key={i}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </figure>
  );
};

export default ExpertSampleBlock;
