import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading } from '@jonathan/ui-react';

import BorderTable from '@src/components/molecules/BorderTable';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getJudgeResult } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './JudgeEvaluation.module.scss';

const cx = classNames.bind(style);

const POLL_MS = 3000;
const POLL_MAX = 60; // judge 는 샘플×provider 호출이라 벤치마크보다 여유

// 결과 상태를 조나단 Badge type으로 매핑한다.
const STATUS_BADGE_TYPE = {
  running: 'blue',
  completed: 'green',
  failed: 'red',
};
const STATUS_LABEL_KEY = {
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
  failed: 'evaluation.failed',
};

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

  // 결과 metrics 의 judge_<criterion> 키에서 기준 도출 → fallback(런 설정) → 빈 목록.
  const derived = results
    ? Object.keys(results)
        .filter((key) => key.startsWith('judge_'))
        .map((key) => key.slice('judge_'.length))
    : [];
  const criteria =
    derived.length > 0
      ? derived
      : Array.isArray(fallbackCriteria)
        ? fallbackCriteria
        : [];
  const critScore = (criterion) => results?.[`judge_${criterion}`];
  const rows = criteria.map((criterion) => {
    const score = critScore(criterion);
    return {
      criterion,
      label: t(`evaluation.judge.criteria.${criterion}`, {
        defaultValue: criterion,
      }),
      score,
      displayScore: typeof score === 'number' ? score.toFixed(2) : '-',
    };
  });
  const columns = useMemo(
    () => [
      {
        name: t('evaluation.judge.criteriaTitle'),
        selector: 'label',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-label')}>{row.label}</span>
        ),
      },
      {
        name: t('evaluation.bench.score'),
        selector: 'score',
        sortable: false,
        cell: (row) => (
          <span className={cx('table-score')}>{row.displayScore}</span>
        ),
      },
    ],
    [t],
  );

  const resultStatus = failed
    ? 'failed'
    : results
      ? 'completed'
      : loading
        ? 'running'
        : 'failed';
  const statusBadge = (
    <div className={cx('result-status')}>
      <Badge
        label={t(STATUS_LABEL_KEY[resultStatus])}
        type={STATUS_BADGE_TYPE[resultStatus]}
        size='sm'
      />
    </div>
  );

  if (failed) {
    return (
      <div className={cx('judge-result')}>
        {statusBadge}
        <EmptyBox
          text='evaluation.judge.failed'
          isBox
          isRed
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }
  if (loading && !results) {
    return (
      <div className={cx('judge-result')}>
        {statusBadge}
        <div className={cx('result-loading')}>
          <Loading />
          <span>{t('evaluation.running')}</span>
        </div>
      </div>
    );
  }
  if (!results) {
    return (
      <div className={cx('judge-result')}>
        {statusBadge}
        <EmptyBox
          text='evaluation.poll.timeout'
          isBox
          customStyle={{ height: '120px' }}
        />
      </div>
    );
  }

  return (
    <div className={cx('judge-result')}>
      {statusBadge}

      <section className={cx('result-section')}>
        <h3 className={cx('result-section-title')}>
          {t('evaluation.results')}
        </h3>
        {criteria.length === 0 ? (
          <EmptyBox
            text='evaluate.empty'
            isBox
            customStyle={{ height: '120px' }}
          />
        ) : (
          <div className={cx('crit-scores')}>
            {rows.map((row) => (
              <div key={row.criterion} className={cx('crit-card')}>
                <div className={cx('crit-name')}>{row.label}</div>
                <div className={cx('crit-value')}>{row.displayScore}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {criteria.length > 0 && (
        <section className={cx('result-section')}>
          <h3 className={cx('result-section-title')}>
            {t('evaluation.results')}
          </h3>
          <div className={cx('result-table')}>
            <BorderTable
              columns={columns}
              data={rows}
              loading={false}
              selectableRows={false}
              hideSearchBox
              hideButtons
              fixedHeader
              fixedHeaderScrollHeight='480px'
            />
          </div>
        </section>
      )}
    </div>
  );
};

export default JudgeResultView;
