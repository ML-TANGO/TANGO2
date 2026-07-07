import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getJudgeResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './JudgeEvaluation.module.scss';

const cx = classNames.bind(style);

const POLL_MS = 3000;
const POLL_MAX = 60; // judge 는 샘플×provider 호출이라 벤치마크보다 여유

// judge run 결과 뷰(프로젝트 상세 진입). getJudgeResult(modelId, jobId) 폴링 → 기준별 점수.
// 표시 기준은 결과 metrics 의 judge_* 키에서 도출(런마다 다른 기준 대응), 미도착 시 fallbackCriteria.
const JudgeResultView = ({ modelId, jobId, fallbackCriteria, onComplete }) => {
  const { t } = useTranslation();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const pollRef = useRef({ alive: true, timer: null });
  const completedRef = useRef(false);

  useEffect(() => {
    const ref = pollRef.current;
    ref.alive = true;
    completedRef.current = false;
    setResults(null);
    setFailed(false);
    setLoading(true);

    const poll = (attempt) => {
      if (!ref.alive) return;
      getJudgeResult(modelId, jobId).then((res) => {
        if (!ref.alive) return;
        if (res.status !== STATUS_SUCCESS) {
          setLoading(false);
          errorToastMessage(res.error, res.message);
          return;
        }
        const r = res.result || {};
        if (r.status === 'failed' || r.status === 'cancelled') {
          setLoading(false);
          setFailed(true);
          return;
        }
        if (r.ready) {
          setResults(r.metrics || {});
          setLoading(false);
          if (!completedRef.current) {
            completedRef.current = true;
            onComplete?.();
          }
          return;
        }
        if (attempt >= POLL_MAX) {
          setLoading(false);
          errorToastMessage(null, t('evaluation.poll.timeout'));
          return;
        }
        ref.timer = setTimeout(() => poll(attempt + 1), POLL_MS);
      });
    };
    poll(0);

    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
  }, [modelId, jobId, t, onComplete]);

  if (failed) {
    return <div className={cx('empty')}>{t('evaluation.judge.failed')}</div>;
  }
  if (loading && !results) {
    return <div className={cx('empty')}>{t('evaluation.running')}</div>;
  }
  if (!results) {
    return <div className={cx('empty')}>{t('evaluation.poll.timeout')}</div>;
  }

  // 결과 metrics 의 judge_<criterion> 키에서 기준 도출 → fallback(런 설정) → 빈 목록.
  const derived = Object.keys(results)
    .filter((k) => k.startsWith('judge_'))
    .map((k) => k.slice('judge_'.length));
  const criteria =
    derived.length > 0
      ? derived
      : Array.isArray(fallbackCriteria)
        ? fallbackCriteria
        : [];
  const critScore = (c) => results[`judge_${c}`];

  return (
    <div className={cx('judge')}>
      <section className={cx('section')}>
        <h3 className={cx('section-title')}>{t('evaluation.results')}</h3>
        {criteria.length === 0 ? (
          <p className={cx('empty')}>{t('evaluate.empty')}</p>
        ) : (
          <div className={cx('crit-scores')}>
            {criteria.map((c) => {
              const v = critScore(c);
              const label = t(`evaluation.judge.criteria.${c}`, {
                defaultValue: c,
              });
              return (
                <div key={c} className={cx('crit-card')}>
                  <div className={cx('crit-name')}>{label}</div>
                  <div className={cx('crit-value')}>
                    {typeof v === 'number' ? v.toFixed(2) : '-'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

export default JudgeResultView;
