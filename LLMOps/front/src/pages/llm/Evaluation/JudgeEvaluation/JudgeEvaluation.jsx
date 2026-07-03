import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';

import EvalComparison from '../EvalComparison/EvalComparison';

import {
  getEvalDatasets,
  getEvalResults,
  getJudgeResult,
  getJudges,
  runJudge,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './JudgeEvaluation.module.scss';

const cx = classNames.bind(style);

// 기준 4종(§14.3). 라벨은 i18n. BE judge_<id> 로 저장(벤치마크 메트릭과 컬럼 분리).
const CRITERIA = ['accuracy', 'relevance', 'fluency', 'safety'];
const POLL_MS = 3000;
const POLL_MAX = 60; // judge 는 샘플×provider 호출이라 벤치마크보다 여유
const MAX_DATASETS = 10;

// LLM-as-a-Judge(llm_evaluation P2). 대상 모델 + 심판(상용 키 / 로컬 URL) + 데이터셋(다중)
//   + 기준(다중) + 커스텀 프롬프트 → judge 런 → poll → 기준별 점수 + 모델 이력 비교표.
//   ⚠️ api_key/base_url 은 화면 state 에만(transient) — 절대 영속하지 않음.
const JudgeEvaluation = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [judges, setJudges] = useState(null); // { commercial, local, criteria, mock }
  const [datasets, setDatasets] = useState([]);
  const [modelId, setModelId] = useState(null);
  const [selDatasets, setSelDatasets] = useState([]);
  const [datasetKeyword, setDatasetKeyword] = useState('');
  const [judgeType, setJudgeType] = useState('commercial'); // commercial | local
  const [provider, setProvider] = useState('chatgpt');
  const [apiKey, setApiKey] = useState(''); // transient
  const [baseUrl, setBaseUrl] = useState('');
  const [judgeModel, setJudgeModel] = useState('');
  const [selCriteria, setSelCriteria] = useState(['accuracy', 'relevance']);
  const [customPrompt, setCustomPrompt] = useState('');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null); // 직전 런 기준별 점수
  const [evalHistory, setEvalHistory] = useState(null);
  const pollRef = useRef({ alive: true, timer: null });

  useEffect(() => {
    pollRef.current.alive = true;
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    (async () => {
      const [dsRes, jRes] = await Promise.all([
        getEvalDatasets(workspaceId),
        getJudges(),
      ]);
      if (dsRes.status === STATUS_SUCCESS) {
        const raw = Array.isArray(dsRes.result)
          ? dsRes.result
          : (dsRes.result?.list ?? []);
        setDatasets(
          raw
            .map((d) => ({
              id: d.id ?? d.dataset_id,
              name: d.name ?? d.dataset_name,
            }))
            .filter((d) => d.id != null),
        );
      }
      if (jRes.status === STATUS_SUCCESS) setJudges(jRes.result);
    })();
    const ref = pollRef.current;
    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
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

  const toggle = (arr, setArr, v) =>
    setArr(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  const toggleDataset = (id) => {
    if (selDatasets.includes(id)) {
      setSelDatasets(selDatasets.filter((x) => x !== id));
      return;
    }
    if (selDatasets.length >= MAX_DATASETS) {
      errorToastMessage(
        null,
        t('evaluation.datasetCap', { max: MAX_DATASETS }),
      );
      return;
    }
    setSelDatasets([...selDatasets, id]);
  };

  const filteredDatasets = useMemo(() => {
    const kw = datasetKeyword.trim().toLowerCase();
    if (!kw) return datasets;
    return datasets.filter((d) => (d.name || '').toLowerCase().includes(kw));
  }, [datasets, datasetKeyword]);

  const mock = !!judges?.mock;
  // 상용=키 필요(mock 면 생략 가능) / 로컬=URL 필요(BE SSRF 검증).
  const providerOk =
    judgeType === 'commercial'
      ? mock || apiKey.trim().length > 0
      : baseUrl.trim().length > 0;
  const canRun =
    !!modelId &&
    selDatasets.length > 0 &&
    selDatasets.length <= MAX_DATASETS &&
    selCriteria.length > 0 &&
    providerOk &&
    !running;

  const poll = useCallback(
    (mId, jobId, attempt) => {
      if (!pollRef.current.alive) return;
      getJudgeResult(mId, jobId).then((res) => {
        if (!pollRef.current.alive) return;
        if (res.status !== STATUS_SUCCESS) {
          setRunning(false);
          errorToastMessage(res.error, res.message);
          return;
        }
        const r = res.result || {};
        if (r.status === 'failed' || r.status === 'cancelled') {
          setRunning(false);
          errorToastMessage(null, t('evaluation.judge.failed'));
          return;
        }
        if (r.ready) {
          setResults(r.metrics);
          setRunning(false);
          fetchHistory(mId); // 새 judge 런이 이력 비교표에도 반영
          return;
        }
        if (attempt >= POLL_MAX) {
          setRunning(false);
          errorToastMessage(null, t('evaluation.poll.timeout'));
          return;
        }
        pollRef.current.timer = setTimeout(
          () => poll(mId, jobId, attempt + 1),
          POLL_MS,
        );
      });
    },
    [t, fetchHistory],
  );

  const handleRun = async () => {
    if (!canRun) return;
    setRunning(true);
    setResults(null);
    const body = {
      model_id: Number(modelId),
      dataset_ids: selDatasets,
      provider: judgeType === 'local' ? 'local' : provider,
      criteria: selCriteria,
      custom_prompt: customPrompt || undefined,
    };
    if (judgeType === 'commercial') {
      body.api_key = apiKey || undefined; // transient — 보내고 화면 state 외 보관 X
    } else {
      body.base_url = baseUrl;
      body.judge_model = judgeModel || undefined;
    }
    const res = await runJudge(body);
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      setRunning(false);
      errorToastMessage(res.error, res.message);
      return;
    }
    poll(Number(modelId), res.result.job_id, 0);
  };

  const commercial = judges?.commercial ?? [];
  // 기준별 점수(judge_<id>) 추출 — results 는 BE metrics({judge_accuracy: 82.5, ...}).
  const critScore = (c) => results?.[`judge_${c}`];

  return (
    <div className={cx('judge')}>
      <div className={cx('header')}>
        <button
          type='button'
          className={cx('back-btn')}
          onClick={() =>
            history.push(`/user/workspace/${workspaceId}/evaluation`)
          }
        >
          ← {t('evaluation.backToHub')}
        </button>
        <h1 className={cx('title')}>{t('evaluation.judge.title')}</h1>
        {mock && <span className={cx('mock-badge')}>mock</span>}
      </div>

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
          {t('evaluation.judge.selectJudge')}
        </h3>
        <div className={cx('tabs')}>
          <button
            type='button'
            className={cx('tab', judgeType === 'commercial' && 'active')}
            onClick={() => setJudgeType('commercial')}
          >
            {t('evaluation.judge.commercial')}
          </button>
          <button
            type='button'
            className={cx('tab', judgeType === 'local' && 'active')}
            onClick={() => setJudgeType('local')}
          >
            {t('evaluation.judge.local')}
          </button>
        </div>

        {judgeType === 'commercial' ? (
          <>
            <div className={cx('judge-cards')}>
              {commercial.map((j) => (
                <button
                  key={j.id}
                  type='button'
                  className={cx('judge-card', provider === j.id && 'selected')}
                  onClick={() => setProvider(j.id)}
                >
                  <span className={cx('judge-label')}>{j.label}</span>
                  <span className={cx('judge-model')}>{j.model}</span>
                </button>
              ))}
            </div>
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                {t('evaluation.judge.apiKey')}
              </label>
              <input
                className={cx('field-input')}
                type='password'
                placeholder={mock ? t('evaluation.judge.apiKeyMock') : 'sk-...'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete='off'
              />
              <p className={cx('field-hint')}>
                {t('evaluation.judge.keyHint')}
              </p>
            </div>
          </>
        ) : (
          <>
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                {t('evaluation.judge.endpoint')}
              </label>
              <input
                className={cx('field-input')}
                type='text'
                placeholder='http://my-llm.example.com/v1'
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
              <p className={cx('field-hint')}>
                {t('evaluation.judge.endpointHint')}
              </p>
            </div>
            <div className={cx('field')}>
              <label className={cx('field-label')}>
                {t('evaluation.judge.modelName')}
              </label>
              <input
                className={cx('field-input')}
                type='text'
                placeholder='llama3-8b-instruct'
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
              />
            </div>
          </>
        )}
      </section>

      <section className={cx('section')}>
        <div className={cx('ds-section-header')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.selectDatasets')}
          </h3>
          <span className={cx('ds-count-badge')}>{datasets.length}</span>
          <div className={cx('ds-spacer')} />
          {selDatasets.length > 0 && (
            <span className={cx('ds-selected-label')}>
              <strong>{selDatasets.length}</strong> / {MAX_DATASETS}
            </span>
          )}
        </div>
        {datasets.length > 0 && (
          <div className={cx('ds-search-wrap')}>
            <input
              className={cx('ds-search-input')}
              placeholder={t('evaluation.searchDataset')}
              value={datasetKeyword}
              onChange={(e) => setDatasetKeyword(e.target.value)}
            />
            {datasetKeyword && (
              <button
                type='button'
                className={cx('ds-search-clear')}
                onClick={() => setDatasetKeyword('')}
              >
                ✕
              </button>
            )}
          </div>
        )}
        {datasets.length === 0 ? (
          <p className={cx('empty')}>{t('evaluation.noDatasets')}</p>
        ) : filteredDatasets.length === 0 ? (
          <div className={cx('ds-empty')}>{t('evaluation.noSearchResult')}</div>
        ) : (
          <div className={cx('ds-list')}>
            {filteredDatasets.map((d) => {
              const isSel = selDatasets.includes(d.id);
              return (
                <div
                  key={d.id}
                  className={cx('ds-card', isSel && 'ds-card--on')}
                  onClick={() => toggleDataset(d.id)}
                >
                  <div className={cx('ds-check', isSel && 'ds-check--on')}>
                    {isSel && '✓'}
                  </div>
                  <div className={cx('ds-card-body')}>
                    <div className={cx('ds-card-name')}>{d.name}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>
          {t('evaluation.judge.criteriaTitle')}
        </h3>
        <div className={cx('chip-row')}>
          {CRITERIA.map((c) => (
            <button
              key={c}
              type='button'
              className={cx('chip', selCriteria.includes(c) && 'selected')}
              onClick={() => toggle(selCriteria, setSelCriteria, c)}
            >
              {t(`evaluation.judge.criteria.${c}`)}
            </button>
          ))}
        </div>
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>{t('evaluation.judge.prompt')}</h3>
        <textarea
          className={cx('prompt')}
          rows={3}
          placeholder={t('evaluation.judge.promptPlaceholder')}
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
        />
      </section>

      <div className={cx('run-row')}>
        <button
          type='button'
          className={cx('run-btn', !canRun && 'disabled')}
          disabled={!canRun}
          onClick={handleRun}
        >
          {running ? t('evaluation.running') : t('evaluation.judge.run')}
        </button>
      </div>

      {results && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>{t('evaluation.results')}</h3>
          <div className={cx('crit-scores')}>
            {selCriteria.map((c) => {
              const v = critScore(c);
              return (
                <div key={c} className={cx('crit-card')}>
                  <div className={cx('crit-name')}>
                    {t(`evaluation.judge.criteria.${c}`)}
                  </div>
                  <div className={cx('crit-value')}>
                    {typeof v === 'number' ? v.toFixed(2) : '-'}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {modelId && (
        <section className={cx('section')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.history.title')}
          </h3>
          <EvalComparison comparison={evalHistory} />
        </section>
      )}
    </div>
  );
};

export default JudgeEvaluation;
