import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import ModelSelector from '@src/components/ModelSelector/ModelSelector';

import EvalComparison from '../EvalComparison/EvalComparison';

import {
  getEvalDatasets,
  getEvalResult,
  getEvalResults,
  runBenchmark,
} from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './BenchmarkEvaluation.module.scss';

const cx = classNames.bind(style);

// ETRI BenchmarkEvaluationPage 정본 17 메트릭(id = llm_evaluation BE/컨테이너와 일치).
// desc = 목업 정본 문구(옵션 카드 표시용). label 은 기존과 동일.
const METRICS = [
  { id: 'accuracy', label: 'Accuracy', desc: '전체 정답률' },
  { id: 'f1', label: 'F1 Score', desc: 'Precision과 Recall의 조화평균' },
  { id: 'acc_norm', label: 'ACC_NORM', desc: '정규화된 정확도' },
  { id: 'arc', label: 'ARC', desc: 'AI2 Reasoning Challenge' },
  { id: 'kobest', label: 'KoBEST', desc: '한국어 NLU 벤치마크' },
  { id: 'mmlu', label: 'MMLU', desc: '다분야 언어 이해 (57개 과목)' },
  { id: 'hellaswag', label: 'HellaSwag', desc: '상식 추론 — 문장 완성' },
  { id: 'winogrande', label: 'WinoGrande', desc: '상식 추론 — 대명사 해소' },
  { id: 'gsm8k', label: 'GSM8K', desc: '초등 수학 문제 풀기' },
  { id: 'truthfulqa', label: 'TruthfulQA', desc: '사실 정확성 평가' },
  { id: 'boolq', label: 'BoolQ', desc: '예/아니오 질의응답' },
  { id: 'humaneval', label: 'HumanEval', desc: '코드 생성 능력 평가' },
  { id: 'meteor', label: 'METEOR', desc: '번역/생성 품질 — 단어 정렬 기반' },
  { id: 'cider', label: 'CIDEr', desc: '이미지 캡셔닝 품질 — TF-IDF 가중치' },
  { id: 'spice', label: 'SPICE', desc: '장면 그래프 기반 의미 유사도' },
  { id: 'bleu', label: 'BLEU', desc: 'N-gram 정밀도 기반 번역 품질' },
  { id: 'rouge', label: 'ROUGE-L', desc: '최장 공통 부분 수열 기반 요약 품질' },
];
const METRIC_LABEL = Object.fromEntries(METRICS.map((m) => [m.id, m.label]));
const POLL_MS = 3000;
const POLL_MAX = 40; // ~2분 (mock 짧지만 컨테이너 기동 여유)
const MAX_DATASETS = 10; // llm_evaluation dto max_length=10 (초과 시 BE 422)

// 숫자 포맷 — 벤치마크 메트릭은 스케일 혼재(accuracy 0-100 vs perplexity 등)라 % 강제 X.
const fmt = (v) => {
  if (v == null) return '-';
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
};
// 막대 폭은 0-100 클램프(비율 외 메트릭이 넘쳐 레이아웃 깨지는 것 방지 — 시각 근사).
const barWidth = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
};

// 벤치마크 평가(llm_evaluation P1c). 모델 + 데이터셋(다중) + 17메트릭(다중) → 런 생성
//   → metrics.json poll → 데이터셋×메트릭 점수표 + 메트릭 평균. ETRI 목업 레이아웃 이식,
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
  const [datasetKeyword, setDatasetKeyword] = useState('');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [evalHistory, setEvalHistory] = useState(null); // 모델 중심 이력 비교표(§14.12)
  const pollRef = useRef({ alive: true, timer: null });

  // 선택 모델의 평가 이력(비교표) 조회 — 모델 선택 시 + 런 완료 후 갱신.
  const fetchHistory = useCallback(async (mId) => {
    if (!mId) return;
    const res = await getEvalResults(mId);
    if (res.status === STATUS_SUCCESS) setEvalHistory(res.result);
  }, []);

  // 모델 변경 시 이력 재조회(이전 모델 이력 잔상 방지).
  useEffect(() => {
    setEvalHistory(null);
    if (modelId) fetchHistory(modelId);
  }, [modelId, fetchHistory]);

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
          : (res.result?.list ?? []);
        setDatasets(
          raw
            .map((d) => ({
              id: d.id ?? d.dataset_id,
              name: d.name ?? d.dataset_name,
              format: d.format ?? d.data_format ?? null,
            }))
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
        // 컨테이너 실패/취소를 DB 상태로 조기 감지(파일 미생성 → 무한폴링 방지).
        if (r.status === 'failed' || r.status === 'cancelled') {
          setRunning(false);
          errorToastMessage(null, t('evaluation.failed'));
          return;
        }
        if (r.ready) {
          setResults(r.metrics);
          setRunning(false);
          fetchHistory(mId); // 새 런이 이력 비교표에도 반영(eval_result lazy 마감 후)
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
  const resultDatasets = Array.isArray(results?.datasets)
    ? results.datasets
    : [];
  const resultMetrics = Array.isArray(results?.metric_set)
    ? results.metric_set
    : selMetrics;
  // 랭킹/차트용: 유한 평균만 내림차순. 표는 전체 메트릭 유지.
  const metricAverages = resultMetrics
    .map((m) => ({ id: m, label: METRIC_LABEL[m] || m, avg: averages[m] }))
    .filter((m) => Number.isFinite(Number(m.avg)))
    .sort((a, b) => Number(b.avg) - Number(a.avg));

  return (
    <div className={cx('benchmark')}>
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
                    <div className={cx('ds-card-name-row')}>
                      <span className={cx('ds-card-name')}>{d.name}</span>
                      {d.format && (
                        <span className={cx('ds-format-badge')}>
                          {d.format}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className={cx('section')}>
        <div className={cx('ds-section-header')}>
          <h3 className={cx('section-title')}>
            {t('evaluation.selectMetrics')} (17)
          </h3>
          {selMetrics.length > 0 && (
            <span className={cx('ds-count-badge')}>{selMetrics.length}</span>
          )}
        </div>
        <div className={cx('option-grid')}>
          {METRICS.map((m) => (
            <div
              key={m.id}
              className={cx(
                'option-card',
                selMetrics.includes(m.id) && 'selected',
              )}
              onClick={() => toggle(selMetrics, setSelMetrics, m.id)}
            >
              <div className={cx('option-name')}>{m.label}</div>
              <div className={cx('option-desc')}>{m.desc}</div>
            </div>
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
        <>
          {metricAverages.length > 0 && (
            <section className={cx('section')}>
              <h3 className={cx('section-title')}>
                {t('evaluation.metricRanking')}
                {results.mock && <span className={cx('mock-badge')}>mock</span>}
              </h3>
              <div className={cx('score-grid')}>
                {metricAverages.map((m, i) => (
                  <div key={m.id} className={cx('score-card')}>
                    <div className={cx('score-rank')}>#{i + 1}</div>
                    <div className={cx('score-metric')}>{m.label}</div>
                    <div className={cx('score-value')}>{fmt(m.avg)}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {metricAverages.length > 0 && (
            <section className={cx('section')}>
              <h3 className={cx('section-title')}>
                {t('evaluation.metricChart')}
              </h3>
              <div className={cx('chart-wrap')}>
                {metricAverages.map((m) => (
                  <div key={m.id} className={cx('chart-row')}>
                    <div className={cx('chart-label')}>{m.label}</div>
                    <div className={cx('chart-bar-wrap')}>
                      <div
                        className={cx('chart-bar')}
                        style={{ width: `${barWidth(m.avg)}%` }}
                      />
                    </div>
                    <div className={cx('chart-value')}>{fmt(m.avg)}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className={cx('section')}>
            <h3 className={cx('section-title')}>{t('evaluation.results')}</h3>
            <div className={cx('table-wrap')}>
              <table className={cx('result-table')}>
                <thead>
                  <tr>
                    <th>{t('evaluation.metric')}</th>
                    {resultDatasets.map((ds) => (
                      <th key={ds}>{ds}</th>
                    ))}
                    <th>{t('evaluation.average')}</th>
                  </tr>
                </thead>
                <tbody>
                  {resultMetrics.map((m) => (
                    <tr key={m}>
                      <td className={cx('metric-cell')}>
                        {METRIC_LABEL[m] || m}
                      </td>
                      {resultDatasets.map((ds) => (
                        <td key={ds} className={cx('score')}>
                          {fmt(scores[ds]?.[m])}
                        </td>
                      ))}
                      <td className={cx('score', 'avg')}>{fmt(averages[m])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
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

export default BenchmarkEvaluation;
