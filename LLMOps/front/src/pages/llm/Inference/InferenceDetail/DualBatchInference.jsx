import { useCallback, useEffect, useRef, useState } from 'react';

import {
  getPlaygroundTestOptions,
  getPlaygroundTestDataset,
  postDualBatch,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './DualBatchInference.module.scss';

const cx = classNames.bind(style);

// 이중모델 데이터셋 일괄 추론(WBS 4.3 배치, 목업 InferenceDetailPage 배치모드 포팅).
//   데이터셋 선택 → 샘플 수 → 메트릭 → 일괄 실행(LLM1→LLM2 체인 N회) → 결과(요약+표).
//   메트릭은 BE 인-프로세스 BLEU/ROUGE(자체메트릭). 동기 배치라 샘플 수 상한 10(실체 부여:
//   목업 [10,50,100,500]→[3,5,10]). SPICE/METEOR/CIDEr(목업)는 벤치 컨테이너 전용→미노출.
const SAMPLE_COUNTS = [3, 5, 10];
const METRICS = [
  { id: 'bleu', label: 'BLEU', keys: ['bleu'] },
  { id: 'rouge', label: 'ROUGE', keys: ['rouge1', 'rouge2', 'rougeL'] },
];
const METRIC_COLS = [
  { key: 'bleu', label: 'BLEU' },
  { key: 'rouge1', label: 'ROUGE-1' },
  { key: 'rouge2', label: 'ROUGE-2' },
  { key: 'rougeL', label: 'ROUGE-L' },
];

const DualBatchInference = ({ playgroundId }) => {
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState(null);
  const [files, setFiles] = useState([]);
  const [filename, setFilename] = useState(null);
  const [sampleCount, setSampleCount] = useState(5);
  const [selectedMetrics, setSelectedMetrics] = useState(['bleu', 'rouge']);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null); // { samples, summary, has_reference, metric_set }
  const runningRef = useRef(false);

  const fetchDatasets = useCallback(async () => {
    const res = await getPlaygroundTestOptions(playgroundId);
    if (res.status === STATUS_SUCCESS) {
      setDatasets(res.result?.dataset_list ?? []);
    } else {
      errorToastMessage(res.error, res.message);
    }
  }, [playgroundId]);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const handleDatasetSelect = async (id) => {
    setDatasetId(id);
    setFilename(null);
    setFiles([]);
    const res = await getPlaygroundTestDataset(id);
    if (res.status === STATUS_SUCCESS) {
      const list = Array.isArray(res.result) ? res.result : [];
      setFiles(list);
      if (list.length) setFilename(list[0].file_name); // 기본 첫 파일
    } else {
      errorToastMessage(res.error, res.message);
    }
  };

  const toggleMetric = (id) =>
    setSelectedMetrics((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  // 결과 렌더는 BE 가 실제 사용한 metric_set 기준(FE 에서 전체 해제해도 BE 기본값과 정합)
  const shownMetrics = result?.metric_set ?? selectedMetrics;
  const activeMetricCols = METRIC_COLS.filter((col) =>
    shownMetrics.some((m) => METRICS.find((x) => x.id === m)?.keys.includes(col.key)),
  );

  const handleRun = async () => {
    if (!datasetId || !filename || runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    setResult(null);
    try {
      const res = await postDualBatch({
        playground_id: playgroundId,
        test_dataset_id: datasetId,
        test_dataset_filename: filename,
        sample_count: sampleCount,
        metrics: selectedMetrics.length ? selectedMetrics : null,
        session_id: sessionStorage.getItem('loginedSession'),
      });
      if (res.status === STATUS_SUCCESS) {
        setResult(res.result);
        return;
      }
      errorToastMessage(res.error, res.message);
    } catch (err) {
      errorToastMessage(null, '일괄 추론 중 오류가 발생했습니다.');
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  };

  return (
    <div className={cx('panel')}>
      <section className={cx('section')}>
        <h3 className={cx('section-title')}>데이터셋 선택</h3>
        {datasets.length === 0 ? (
          <p className={cx('empty')}>사용 가능한 데이터셋이 없습니다.</p>
        ) : (
          <div className={cx('ds-list')}>
            {datasets.map((d) => {
              const sel = String(datasetId) === String(d.id);
              return (
                <div
                  key={d.id}
                  className={cx('ds-item', sel && 'selected')}
                  onClick={() => handleDatasetSelect(d.id)}
                >
                  <span className={cx('ds-radio', sel && 'on')} />
                  <span className={cx('ds-name')}>{d.name}</span>
                </div>
              );
            })}
          </div>
        )}
        {files.length > 1 && (
          <select
            className={cx('file-select')}
            aria-label="데이터셋 파일"
            value={filename ?? ''}
            onChange={(e) => setFilename(e.target.value)}
          >
            {files.map((f) => (
              <option key={f.file_name} value={f.file_name}>
                {f.file_name}
              </option>
            ))}
          </select>
        )}
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>샘플 수</h3>
        <div className={cx('chip-row')}>
          {SAMPLE_COUNTS.map((n) => (
            <div
              key={n}
              className={cx('chip', sampleCount === n && 'selected')}
              onClick={() => setSampleCount(n)}
            >
              {n}개
            </div>
          ))}
        </div>
        <p className={cx('note')}>* 동기 배치라 최대 10개까지 (샘플당 프롬프트→추론 2회 호출).</p>
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>정량 메트릭 (reference 필요)</h3>
        <div className={cx('chip-row')}>
          {METRICS.map((m) => (
            <div
              key={m.id}
              className={cx('chip', selectedMetrics.includes(m.id) && 'selected')}
              onClick={() => toggleMetric(m.id)}
            >
              {m.label}
            </div>
          ))}
        </div>
      </section>

      <div className={cx('run-row')}>
        <button
          type="button"
          className={cx('run-btn', (!datasetId || !filename || running) && 'disabled')}
          disabled={!datasetId || !filename || running}
          onClick={handleRun}
        >
          {running ? '일괄 추론 실행 중...' : '일괄 추론 실행'}
        </button>
      </div>

      {result && (
        <div className={cx('results')}>
          {!result.has_reference && (
            <p className={cx('note')}>
              데이터셋에 reference 컬럼이 없어 메트릭은 산출하지 않았습니다 (출력만 표시).
            </p>
          )}
          {result.has_reference && result.summary && (
            <div className={cx('summary-box')}>
              <h3 className={cx('summary-title')}>종합 결과 (평균)</h3>
              <div className={cx('summary-metrics')}>
                {activeMetricCols.map(
                  (col) =>
                    result.summary[col.key] != null && (
                      <div key={col.key} className={cx('summary-metric')}>
                        <span className={cx('sm-label')}>{col.label}</span>
                        <span className={cx('sm-value')}>
                          {result.summary[col.key]}
                        </span>
                      </div>
                    ),
                )}
              </div>
            </div>
          )}
          <div className={cx('table-wrap')}>
            <table className={cx('result-table')}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>입력</th>
                  <th>출력</th>
                  {result.has_reference && <th>정답</th>}
                  {result.has_reference &&
                    activeMetricCols.map((col) => <th key={col.key}>{col.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {(result.samples ?? []).map((s, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td className={cx('cell-text')}>{s.input}</td>
                    <td className={cx('cell-text')}>{s.output}</td>
                    {result.has_reference && (
                      <td className={cx('cell-text')}>{s.reference || '-'}</td>
                    )}
                    {result.has_reference &&
                      activeMetricCols.map((col) => (
                        <td key={col.key} className={cx('score')}>
                          {s[col.key] != null ? s[col.key] : '-'}
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default DualBatchInference;
