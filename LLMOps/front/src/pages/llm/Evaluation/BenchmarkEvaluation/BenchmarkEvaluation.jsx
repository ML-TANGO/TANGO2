import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';

import {
  getEvalDatasets,
  getEvalResult,
  runBenchmark,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// ETRI BenchmarkEvaluationPage 정본 17 메트릭(id = llm_evaluation BE/컨테이너와 일치).
const METRICS = [
  { id: 'accuracy', label: 'Accuracy' },
  { id: 'f1', label: 'F1 Score' },
  { id: 'acc_norm', label: 'ACC_NORM' },
  { id: 'arc', label: 'ARC' },
  { id: 'kobest', label: 'KoBEST' },
  { id: 'mmlu', label: 'MMLU' },
  { id: 'hellaswag', label: 'HellaSwag' },
  { id: 'winogrande', label: 'WinoGrande' },
  { id: 'gsm8k', label: 'GSM8K' },
  { id: 'truthfulqa', label: 'TruthfulQA' },
  { id: 'boolq', label: 'BoolQ' },
  { id: 'humaneval', label: 'HumanEval' },
  { id: 'meteor', label: 'METEOR' },
  { id: 'cider', label: 'CIDEr' },
  { id: 'spice', label: 'SPICE' },
  { id: 'bleu', label: 'BLEU' },
  { id: 'rouge', label: 'ROUGE-L' },
];
const METRIC_LABEL = Object.fromEntries(METRICS.map((m) => [m.id, m.label]));
const POLL_MS = 3000;
const POLL_MAX = 40; // ~2분 (mock 짧지만 컨테이너 기동 여유)
const MAX_DATASETS = 10; // llm_evaluation dto max_length=10 (초과 시 BE 422)

// 벤치마크 평가(llm_evaluation P1c). 모델 + 데이터셋(다중) + 17메트릭(다중) → 런 생성
//   → metrics.json poll → 데이터셋×메트릭 점수표 + 메트릭 평균. ETRI 화면 재배선,
//   실 BE(llm_evaluation /api/evaluations). 컴퓨트는 외부 컨테이너(현재 mock).
const BenchmarkEvaluation = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [datasets, setDatasets] = useState([]);
  const [modelId, setModelId] = useState(null);
  const [selDatasets, setSelDatasets] = useState([]);
  const [selMetrics, setSelMetrics] = useState([]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const pollRef = useRef({ alive: true, timer: null });

  useEffect(() => {
    // workspaceId 변경/재마운트 시 liveness 복원 — cleanup 이 alive=false 로 둔 뒤
    // 재실행 시 poll 이 즉시 bail → 스피너 stuck 되는 것 방지(codex).
    pollRef.current.alive = true;
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    (async () => {
      const res = await getEvalDatasets(workspaceId);
      if (res.status === STATUS_SUCCESS) {
        const raw = Array.isArray(res.result)
          ? res.result
          : res.result?.list ?? [];
        setDatasets(
          raw
            .map((d) => ({ id: d.id ?? d.dataset_id, name: d.name ?? d.dataset_name }))
            .filter((d) => d.id != null),
        );
      } else {
        errorToastMessage(res.error, res.message);
      }
    })();
    const ref = pollRef.current;
    return () => {
      ref.alive = false;
      if (ref.timer) clearTimeout(ref.timer);
    };
  }, [dispatch, workspaceId]);

  const toggle = (arr, setArr, v) =>
    setArr(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  // 데이터셋은 BE cap(10) 클라이언트단 강제 — 초과 추가 시 토스트, 422 round-trip 회피.
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

  const canRun =
    !!modelId &&
    selDatasets.length > 0 &&
    selDatasets.length <= MAX_DATASETS &&
    selMetrics.length > 0 &&
    !running;

  const poll = useCallback(
    (mId, jobId, attempt) => {
      if (!pollRef.current.alive) return;
      getEvalResult(mId, jobId).then((res) => {
        if (!pollRef.current.alive) return;
        // 4xx/5xx 등 실패는 즉시 중단 — not-ready(status=SUCCESS+ready:false)와 구분해
        // 2분 timeout까지 실제 에러를 숨기지 않도록(codex).
        if (res.status !== STATUS_SUCCESS) {
          setRunning(false);
          errorToastMessage(res.error, res.message);
          return;
        }
        const r = res.result || {};
        if (r.ready) {
          setResults(r.metrics);
          setRunning(false);
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
    [t],
  );

  const handleRun = async () => {
    if (!canRun) return;
    setRunning(true);
    setResults(null);
    const res = await runBenchmark({
      model_id: Number(modelId),
      dataset_ids: selDatasets,
      metric_set: selMetrics,
    });
    if (res.status !== STATUS_SUCCESS || !res.result?.job_id) {
      setRunning(false);
      errorToastMessage(res.error, res.message);
      return;
    }
    poll(Number(modelId), res.result.job_id, 0);
  };

  const scores = results?.scores || {};
  const averages = results?.averages || {};
  // 비배열(malformed truthy)이면 .map 크래시 → Array.isArray 방어(codex).
  const resultDatasets = Array.isArray(results?.datasets) ? results.datasets : [];
  const resultMetrics = Array.isArray(results?.metric_set)
    ? results.metric_set
    : selMetrics;

  return (
    <div className={cx('benchmark')}>
      <div className={cx('header')}>
        <button
          type='button'
          className={cx('back-btn')}
          onClick={() => history.push(`/user/workspace/${workspaceId}/evaluation`)}
        >
          ← {t('evaluation.backToHub')}
        </button>
        <h1 className={cx('title')}>{t('evaluation.benchmark.title')}</h1>
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

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>{t('evaluation.selectMetrics')} (17)</h3>
        <div className={cx('chip-row')}>
          {METRICS.map((m) => (
            <button
              key={m.id}
              type='button'
              className={cx('chip', selMetrics.includes(m.id) && 'selected')}
              onClick={() => toggle(selMetrics, setSelMetrics, m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </section>

      <div className={cx('run-row')}>
        <button
          type='button'
          className={cx('run-btn', !canRun && 'disabled')}
          disabled={!canRun}
          onClick={handleRun}
        >
          {running ? t('evaluation.running') : t('evaluation.runBenchmark')}
        </button>
      </div>

      {results && (
        <section className={cx('results')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.results')}
            {results.mock && <span className={cx('mock-badge')}>mock</span>}
          </h3>
          <div className={cx('table-wrap')}>
            <table className={cx('result-table')}>
              <thead>
                <tr>
                  <th>{t('evaluation.dataset')}</th>
                  {resultMetrics.map((m) => (
                    <th key={m}>{METRIC_LABEL[m] || m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {resultDatasets.map((ds) => (
                  <tr key={ds}>
                    <td>{ds}</td>
                    {resultMetrics.map((m) => (
                      <td key={m} className={cx('score')}>
                        {scores[ds]?.[m] ?? '-'}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr className={cx('avg-row')}>
                  <td>{t('evaluation.average')}</td>
                  {resultMetrics.map((m) => (
                    <td key={m} className={cx('score')}>
                      {averages[m] ?? '-'}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};

export default BenchmarkEvaluation;
