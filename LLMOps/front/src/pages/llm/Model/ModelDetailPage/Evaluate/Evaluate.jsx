import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';
import { callApi, STATUS_SUCCESS } from '@src/network';
import {
  getEvaluateJob,
  getEvaluateResult,
  getEvaluateResults,
  markEvaluateStatus,
  startEvaluate,
} from '@src/apis/llm/model';

import SimpleNav from '../SimpleNav';
import EvaluateModal from './EvaluateModal';

import classNames from 'classnames/bind';
import style from './Evaluate.module.scss';

const cx = classNames.bind(style);

const TERMINAL = ['completed', 'failed', 'cancelled'];
const POLL_MS = 3000;
const MAX_POLL_FAILS = 5; // 연속 조회 실패 시 실패 처리(무한 폴링 방지)

const lsKey = (modelId) => `sp5_evaluate_${modelId}`;
const LS_TTL_MS = 24 * 60 * 60 * 1000; // 복원 항목 만료(stale job_id 재폴링 방지)

// fb_external_container ExternalJobDetail 의 partner 상태는 nested result.status.
const readStatus = (detail) =>
  detail?.result?.status || detail?.status || 'pending';

// 메트릭 값 표시 — perplexity 등 큰 수는 정수부, 0~100 스케일은 소수 2자리.
const fmtMetric = (v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return '-';
  return v >= 1000 ? v.toFixed(0) : v.toFixed(2);
};

/**
 * 자동평가 탭 (SP-5 / v0.4 3.8).
 * 학습 완료 모델 → '평가' 버튼 → 데이터셋·메트릭 선택 모달 → evaluate job 폴링 →
 * 완료 시 비교표(메트릭별 best 배지 + SDM 자유 키)에 누적. 자체 메트릭(BLEU/ROUGE/
 * perplexity)은 외부 SaaS judge 비의존. job_id 는 localStorage 에 모델별 저장.
 */
const Evaluate = memo(function Evaluate({ navList, data, ...rest }) {
  const { t } = useTranslation();
  const { modelId, workspaceId } = data;

  const [titleName, setTitleName] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState(null); // { jobId, datasetName }
  const [status, setStatus] = useState(null);
  const [comparison, setComparison] = useState(null); // { metric_keys, best, runs }
  const pollRef = useRef(null);

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // 모델명 (SimpleNav 타이틀용)
  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await callApi({
        url: `models/fine-tuning/summary?model_id=${modelId}`,
        method: 'get',
      });
      if (alive && res.status === STATUS_SUCCESS) setTitleName(res.result?.name ?? '');
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 진행 중이던 job 복원 (localStorage). TTL 초과 항목은 폐기(끝난 job_id 재폴링 방지).
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(lsKey(modelId));
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed?.ts && Date.now() - parsed.ts > LS_TTL_MS) {
        window.localStorage.removeItem(lsKey(modelId));
        return;
      }
      setJob(parsed);
    } catch (e) {
      /* ignore malformed */
    }
  }, [modelId]);

  const fetchComparison = useCallback(async () => {
    const res = await getEvaluateResults(modelId);
    if (res.status === STATUS_SUCCESS) setComparison(res.result);
  }, [modelId]);

  // 평가 비교표 (마운트 시)
  useEffect(() => {
    fetchComparison();
  }, [fetchComparison]);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // job 상태 폴링 → 완료 시 결과 lazy 마감 + 비교표 갱신
  useEffect(() => {
    if (!job?.jobId) return undefined;
    let cancelled = false;
    let failCount = 0;

    const onTerminal = (st) => {
      stopPoll();
      if (cancelled) return;
      // 끝난 job 은 localStorage 에서 제거 — 새로고침 시 종료된 job_id 를 재폴링하다
      // 트래커 cleanup 으로 404→failed 오판하는 것 방지(결과는 비교표가 보존).
      try {
        window.localStorage.removeItem(lsKey(modelId));
      } catch (e) {
        /* ignore */
      }
      if (st === 'completed') {
        // metrics.json 읽어 eval_result lazy 마감 후 비교표 갱신
        getEvaluateResult(modelId, job.jobId).finally(fetchComparison);
      } else {
        markEvaluateStatus(modelId, job.jobId, st).finally(fetchComparison);
      }
    };

    const tick = async () => {
      const res = await getEvaluateJob(job.jobId);
      if (cancelled) return;
      if (res.status !== STATUS_SUCCESS) {
        failCount += 1;
        if (failCount >= MAX_POLL_FAILS) onTerminal('failed');
        return;
      }
      failCount = 0;
      const st = readStatus(res.result);
      setStatus(st);
      if (TERMINAL.includes(st)) onTerminal(st);
    };

    tick();
    pollRef.current = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      stopPoll();
    };
  }, [job, modelId, fetchComparison, stopPoll]);

  const handleLaunch = useCallback(
    async (body) => {
      setSubmitting(true);
      const res = await startEvaluate(modelId, body);
      setSubmitting(false);
      if (res.status === STATUS_SUCCESS && res.result?.job_id) {
        const next = {
          jobId: res.result.job_id,
          datasetName: res.result.dataset_name || '',
          ts: Date.now(),
        };
        try {
          window.localStorage.setItem(lsKey(modelId), JSON.stringify(next));
        } catch (e) {
          /* quota — 무시 */
        }
        setStatus('pending');
        setJob(next);
        setModalOpen(false);
        toast.success(t('evaluate.started'));
        fetchComparison();
      } else {
        toast.error(res.message || t('evaluate.start.fail'));
      }
    },
    [modelId, t, fetchComparison],
  );

  const handleReset = useCallback(() => {
    stopPoll();
    try {
      window.localStorage.removeItem(lsKey(modelId));
    } catch (e) {
      /* ignore */
    }
    setJob(null);
    setStatus(null);
  }, [modelId, stopPoll]);

  const isRunning = job && !TERMINAL.includes(status);
  const isFailed = status === 'failed' || status === 'cancelled';

  const metricKeys = comparison?.metric_keys ?? [];
  const best = comparison?.best ?? {};
  const runs = comparison?.runs ?? [];

  return (
    <div id='evaluate-tab' className={cx('evaluate-tab')}>
      <SimpleNav navList={navList} t={t} {...filteredRest} titleName={titleName} />

      <div className={cx('container')}>
        <div className={cx('intro')}>
          <div className={cx('intro-head')}>
            <div>
              <div className={cx('intro-title')}>{t('evaluate.label')}</div>
              <div className={cx('intro-desc')}>{t('evaluate.intro.desc')}</div>
            </div>
            <ButtonV2
              colorType='blue'
              label={t('evaluate.start.label')}
              onClick={() => setModalOpen(true)}
              disabled={isRunning}
            />
          </div>
        </div>

        {job && (
          <div className={cx('job-card')}>
            <div className={cx('job-row')}>
              <span className={cx('job-label')}>{t('evaluate.dataset.label')}</span>
              <span className={cx('job-value')}>{job.datasetName || '-'}</span>
            </div>
            <div className={cx('job-row')}>
              <span className={cx('job-label')}>{t('evaluate.status.label')}</span>
              <span className={cx('status', isFailed ? 'fail' : status === 'completed' ? 'done' : 'run')}>
                {isRunning && <span className={cx('spinner')} />}
                {t(`evaluate.status.${status || 'pending'}`)}
              </span>
            </div>
            {isFailed && (
              <div className={cx('error-box')}>{t('evaluate.status.failHint')}</div>
            )}
            <div className={cx('job-actions')}>
              <ButtonV2
                type='outline'
                label={t('evaluate.clear.label')}
                onClick={handleReset}
                disabled={isRunning}
              />
            </div>
          </div>
        )}

        {runs.length > 0 ? (
          <div className={cx('comparison')}>
            <div className={cx('comparison-title')}>{t('evaluate.comparison.label')}</div>
            <div className={cx('table-wrap')}>
              <table className={cx('comparison-table')}>
                <thead>
                  <tr>
                    <th>{t('evaluate.dataset.label')}</th>
                    {metricKeys.map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                    <th>{t('evaluate.status.label')}</th>
                    <th>{t('createdAt.label')}</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id}>
                      <td>{run.dataset_name || '-'}</td>
                      {metricKeys.map((k) => {
                        const v = run.metrics?.[k];
                        const isBest = best[k] === run.id && v !== undefined;
                        return (
                          <td key={k} className={cx('metric-cell', isBest && 'best')}>
                            {v !== undefined ? fmtMetric(v) : '-'}
                            {isBest && <span className={cx('best-badge')}>{t('evaluate.best.badge')}</span>}
                          </td>
                        );
                      })}
                      <td className={cx('run-status', run.status)}>
                        {t(`evaluate.status.${run.status || 'pending'}`)}
                      </td>
                      <td>{run.create_datetime || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={cx('comparison-hint')}>{t('evaluate.comparison.hint')}</div>
          </div>
        ) : (
          !job && (
            <div className={cx('empty')}>
              <div className={cx('empty-text')}>{t('evaluate.empty')}</div>
            </div>
          )
        )}
      </div>

      <EvaluateModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={handleLaunch}
        submitting={submitting}
        workspaceId={workspaceId}
      />
    </div>
  );
});

export default Evaluate;
