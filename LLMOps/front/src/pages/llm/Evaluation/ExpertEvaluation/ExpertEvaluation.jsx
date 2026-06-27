import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';

import EvalComparison from '../EvalComparison/EvalComparison';

import {
  getEvalDatasets,
  getEvalResults,
  startExpert,
  submitExpertRating,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ExpertEvaluation.module.scss';

const cx = classNames.bind(style);

const MAX_DATASETS = 10;

// 전문가 평가(llm_evaluation P3). 모델 + 데이터셋 → 샘플(입력/출력/참조)을 사람이 O/X +
//   코멘트로 채점 → eval_expert_rating 영속 → 합격률 집계 → 모델 이력 비교표 합류.
const ExpertEvaluation = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [datasets, setDatasets] = useState([]);
  const [modelId, setModelId] = useState(null);
  const [selDatasets, setSelDatasets] = useState([]);
  const [session, setSession] = useState(null); // { job, samples, total }
  const [ratings, setRatings] = useState({}); // idx → { verdict, comment }
  const [progress, setProgress] = useState(null); // { rated, total, pass_rate, completed }
  const [starting, setStarting] = useState(false);
  const [evalHistory, setEvalHistory] = useState(null);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    (async () => {
      const res = await getEvalDatasets(workspaceId);
      if (res.status === STATUS_SUCCESS) {
        const raw = Array.isArray(res.result) ? res.result : res.result?.list ?? [];
        setDatasets(
          raw
            .map((d) => ({ id: d.id ?? d.dataset_id, name: d.name ?? d.dataset_name }))
            .filter((d) => d.id != null),
        );
      } else {
        errorToastMessage(res.error, res.message);
      }
    })();
  }, [dispatch, workspaceId]);

  const fetchHistory = useCallback(async (mId) => {
    if (!mId) return;
    const res = await getEvalResults(mId);
    if (res.status === STATUS_SUCCESS) setEvalHistory(res.result);
  }, []);

  useEffect(() => {
    setEvalHistory(null);
    if (modelId) fetchHistory(modelId);
  }, [modelId, fetchHistory]);

  const toggleDataset = (id) => {
    if (selDatasets.includes(id)) {
      setSelDatasets(selDatasets.filter((x) => x !== id));
      return;
    }
    if (selDatasets.length >= MAX_DATASETS) {
      errorToastMessage(null, t('evaluation.datasetCap', { max: MAX_DATASETS }));
      return;
    }
    setSelDatasets([...selDatasets, id]);
  };

  const handleStart = async () => {
    if (!modelId || selDatasets.length === 0 || starting) return;
    setStarting(true);
    const res = await startExpert({
      model_id: Number(modelId),
      dataset_ids: selDatasets,
    });
    setStarting(false);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      errorToastMessage(res.error, res.message);
      return;
    }
    setSession(res.result);
    setRatings({});
    setProgress({ rated: 0, total: res.result.total, pass_rate: 0, completed: false });
  };

  const setComment = (idx, comment) =>
    setRatings((prev) => ({ ...prev, [idx]: { ...prev[idx], comment } }));

  const rate = async (idx, verdict) => {
    const comment = ratings[idx]?.comment || '';
    const prevVerdict = ratings[idx]?.verdict;
    setRatings((prev) => ({ ...prev, [idx]: { ...prev[idx], verdict } }));
    const res = await submitExpertRating(Number(modelId), session.job_id, {
      sample_idx: idx,
      verdict,
      comment: comment || undefined,
    });
    if (res.status !== STATUS_SUCCESS) {
      // 서버 반영 실패 → 낙관적 verdict 롤백(버튼 하이라이트 잔상 방지).
      setRatings((prev) => ({ ...prev, [idx]: { ...prev[idx], verdict: prevVerdict } }));
      errorToastMessage(res.error, res.message);
      return;
    }
    setProgress(res.result);
    if (res.result?.completed) fetchHistory(Number(modelId));
  };

  const handleReset = () => {
    setSession(null);
    setRatings({});
    setProgress(null);
  };

  return (
    <div className={cx('expert')}>
      <div className={cx('header')}>
        <button
          type='button'
          className={cx('back-btn')}
          onClick={() => history.push(`/user/workspace/${workspaceId}/evaluation`)}
        >
          ← {t('evaluation.backToHub')}
        </button>
        <h1 className={cx('title')}>{t('evaluation.expert.title')}</h1>
      </div>

      {!session ? (
        <>
          <section className={cx('section')}>
            <h3 className={cx('section-title')}>{t('evaluation.selectModel')}</h3>
            <ModelSelector
              wid={workspaceId}
              selected={modelId}
              onSelect={(id) => setModelId(id)}
            />
          </section>

          <section className={cx('section')}>
            <h3 className={cx('section-title')}>
              {t('evaluation.selectDatasets')} ({selDatasets.length}/{MAX_DATASETS})
            </h3>
            {datasets.length === 0 ? (
              <p className={cx('empty')}>{t('evaluation.noDatasets')}</p>
            ) : (
              <div className={cx('chip-row')}>
                {datasets.map((d) => (
                  <button
                    key={d.id}
                    type='button'
                    className={cx('chip', selDatasets.includes(d.id) && 'selected')}
                    onClick={() => toggleDataset(d.id)}
                  >
                    {d.name}
                  </button>
                ))}
              </div>
            )}
          </section>

          <div className={cx('run-row')}>
            <button
              type='button'
              className={cx('run-btn', (!modelId || selDatasets.length === 0) && 'disabled')}
              disabled={!modelId || selDatasets.length === 0 || starting}
              onClick={handleStart}
            >
              {starting ? t('evaluation.running') : t('evaluation.expert.start')}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className={cx('progress-bar')}>
            <span className={cx('progress-text')}>
              {t('evaluation.expert.progress', {
                rated: progress?.rated ?? 0,
                total: progress?.total ?? session.total,
              })}
            </span>
            <span className={cx('pass-rate')}>
              {t('evaluation.expert.passRate')}: <strong>{progress?.pass_rate ?? 0}%</strong>
            </span>
            {progress?.completed && (
              <span className={cx('done-badge')}>{t('evaluation.expert.completed')}</span>
            )}
            <div className={cx('spacer')} />
            <button type='button' className={cx('reset-btn')} onClick={handleReset}>
              {t('evaluation.expert.newSession')}
            </button>
          </div>

          <div className={cx('samples')}>
            {session.samples.map((s) => {
              const r = ratings[s.idx] || {};
              return (
                <div key={s.idx} className={cx('sample-card')}>
                  <div className={cx('sample-idx')}>#{s.idx + 1}</div>
                  <div className={cx('sample-body')}>
                    <div className={cx('field-row')}>
                      <span className={cx('field-key')}>{t('evaluation.expert.input')}</span>
                      <span className={cx('field-val')}>{s.input}</span>
                    </div>
                    <div className={cx('field-row')}>
                      <span className={cx('field-key')}>{t('evaluation.expert.output')}</span>
                      <span className={cx('field-val')}>{s.output}</span>
                    </div>
                    {s.reference && (
                      <div className={cx('field-row')}>
                        <span className={cx('field-key')}>{t('evaluation.expert.reference')}</span>
                        <span className={cx('field-val', 'ref')}>{s.reference}</span>
                      </div>
                    )}
                    <div className={cx('rate-row')}>
                      <button
                        type='button'
                        className={cx('verdict', 'pass', r.verdict === 'O' && 'on')}
                        onClick={() => rate(s.idx, 'O')}
                      >
                        O {t('evaluation.expert.pass')}
                      </button>
                      <button
                        type='button'
                        className={cx('verdict', 'fail', r.verdict === 'X' && 'on')}
                        onClick={() => rate(s.idx, 'X')}
                      >
                        X {t('evaluation.expert.fail')}
                      </button>
                      <input
                        className={cx('comment')}
                        type='text'
                        placeholder={t('evaluation.expert.commentPlaceholder')}
                        value={r.comment || ''}
                        onChange={(e) => setComment(s.idx, e.target.value)}
                        onBlur={() => {
                          // 이미 채점된 샘플의 코멘트 수정은 blur 시 영속(미완료 세션 한정).
                          if (r.verdict && !progress?.completed) rate(s.idx, r.verdict);
                        }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {modelId && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>{t('evaluation.history.title')}</h3>
          <EvalComparison comparison={evalHistory} />
        </section>
      )}
    </div>
  );
};

export default ExpertEvaluation;
