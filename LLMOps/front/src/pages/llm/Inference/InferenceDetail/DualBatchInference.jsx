import { useCallback, useEffect, useRef, useState } from 'react';

import { useSelector } from 'react-redux';
import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import {
  getPlaygroundTestOptions,
  getPlaygroundTestDataset,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

// SSE 호스트/헤더 규약 — useSSEStatus 와 동일(인증 헤더 필요).
const API_HOST_ENV = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = API_HOST_ENV
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

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

// 외부 SDS(VLM) 배치 출력 형식 — 배치는 데이터셋만 선택하므로 UI 없이 기본값 사용
// (이미지/AIS 는 데이터셋 행의 image·ais_rows 에서 per-sample 로 읽음).
const SDS_BATCH_PARAMS = {
  output_type: '한글 해상상황묘사',
  max_new_tokens: 256,
  repetition_penalty: 1.1,
  do_sample: false,
};

const DualBatchInference = ({ playgroundId, isExternal = false }) => {
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState(null);
  const [files, setFiles] = useState([]);
  const [filename, setFilename] = useState(null);
  const [sampleCount, setSampleCount] = useState(5);
  const [selectedMetrics, setSelectedMetrics] = useState(['bleu', 'rouge']);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null); // { samples, summary, has_reference, metric_set }
  const [progress, setProgress] = useState(null); // { done, total } — SSE 진행률
  const runningRef = useRef(false);
  const esRef = useRef(null); // 진행 중 SSE 연결
  const rowsRef = useRef([]); // 스트리밍 누적 샘플(요약 도착 시 result 로 확정)
  const { userName } = useSelector((state) => state.auth);

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
    shownMetrics.some((m) =>
      METRICS.find((x) => x.id === m)?.keys.includes(col.key),
    ),
  );

  // 스트림 종료(정상/실패 공통) — 재연결하지 않는다(재연결 시 배치가 처음부터 재실행되어 GPU 2배 소모).
  const closeStream = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    runningRef.current = false;
    setRunning(false);
  }, []);

  useEffect(() => closeStream, [closeStream]); // 언마운트 시 스트림 정리

  // 중단/오류 시에도 이미 끝난 샘플(비싼 추론 결과)은 버리지 않고 표에 남긴다.
  //   요약(코퍼스 메트릭)은 서버가 못 보냈으므로 생략하고 부분 결과만 확정.
  const finalizePartial = useCallback(() => {
    if (!rowsRef.current.length) return;
    setResult(
      (prev) =>
        prev ?? {
          samples: rowsRef.current,
          summary: {},
          sample_count: rowsRef.current.length,
          has_reference: false,
          metric_set: [],
          partial: true,
        },
    );
  }, []);

  // 배치는 샘플당 ~16s(LLM1+추론) → 동기 POST 는 게이트웨이 60s 타임아웃에 걸림.
  //   SSE 로 샘플 완료마다 수신하고, 요약 이벤트에서 결과를 확정한다.
  const handleRun = () => {
    if (!datasetId || !filename || runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    setResult(null);
    setProgress(null);
    rowsRef.current = [];

    const params = new URLSearchParams({
      playground_id: String(playgroundId),
      test_dataset_id: String(datasetId),
      test_dataset_filename: filename,
      sample_count: String(sampleCount),
      // session_id 는 query 로 보내지 않는다(URL 에 세션 자격증명 노출) — jf-Session 헤더로 전달.
    });
    if (selectedMetrics.length)
      params.set('metrics', selectedMetrics.join(','));
    // 외부 SDS: 출력 형식만 전달(이미지/AIS 는 데이터셋 행에서 per-sample 로 읽음).
    if (isExternal) params.set('output_type', SDS_BATCH_PARAMS.output_type);

    const es = new EventSourcePolyfill(
      `${API_HOST}playgrounds/dual-batch/sse?${params.toString()}`,
      {
        headers: {
          'Content-Type': 'application/json;charset=UTF-8',
          'jf-User': userName || 'login',
          'jf-Token': sessionStorage.getItem('token') || 'login',
          'jf-Session': sessionStorage.getItem('loginedSession') || 'login',
          Authorization:
            MODE === 'INTEGRATION' ? cookies.get('access_token') : undefined,
        },
        heartbeatTimeout: 30 * 60 * 1000, // 배치 총소요(샘플수×~16s)보다 길게
      },
    );
    esRef.current = es;

    es.onmessage = (event) => {
      if (!event.data || !event.data.trim()) return; // keepalive
      let ev;
      try {
        ev = JSON.parse(event.data);
      } catch (_) {
        return;
      }
      if (ev.type === 'start') {
        setProgress({ done: 0, total: ev.total });
      } else if (ev.type === 'sample') {
        rowsRef.current = [...rowsRef.current, ev];
        setProgress({ done: ev.index, total: ev.total });
      } else if (ev.type === 'summary') {
        setResult({
          samples: rowsRef.current,
          summary: ev.summary,
          sample_count: ev.sample_count,
          has_reference: ev.has_reference,
          metric_set: ev.metric_set,
        });
        closeStream();
      } else if (ev.type === 'error') {
        errorToastMessage(
          null,
          ev.message || '일괄 추론 중 오류가 발생했습니다.',
        );
        finalizePartial();
        closeStream();
      }
    };

    es.onerror = () => {
      if (runningRef.current) {
        errorToastMessage(null, '일괄 추론 연결이 끊어졌습니다.');
        finalizePartial();
      }
      closeStream();
    };
  };

  return (
    <div className={cx('panel')}>
      <section className={cx('section')}>
        <h3 className={cx('section-title')}>데이터셋 선택</h3>
        {isExternal && (
          <p className={cx('note')}>
            * SDS(VLM) 추론은 샘플별 이미지·AIS가 필요합니다. 데이터셋 각 행에
            image(데이터셋 내 상대경로)와 ais_rows(자선 my_ship=1 포함)를 포함해
            주세요.
          </p>
        )}
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
        {/* 데이터셋 안의 파일 선택 — 1개여도 노출(어떤 파일로 추론하는지 명시) */}
        {files.length > 0 && (
          <select
            className={cx('file-select')}
            aria-label='데이터셋 파일'
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
        <p className={cx('note')}>
          * 동기 배치라 최대 10개까지 (샘플당 프롬프트→추론 2회 호출).
        </p>
      </section>

      <section className={cx('section')}>
        <h3 className={cx('section-title')}>정량 메트릭 (reference 필요)</h3>
        <div className={cx('chip-row')}>
          {METRICS.map((m) => (
            <div
              key={m.id}
              className={cx(
                'chip',
                selectedMetrics.includes(m.id) && 'selected',
              )}
              onClick={() => toggleMetric(m.id)}
            >
              {m.label}
            </div>
          ))}
        </div>
      </section>

      <div className={cx('run-row')}>
        <button
          type='button'
          className={cx(
            'run-btn',
            (!datasetId || !filename || running) && 'disabled',
          )}
          disabled={!datasetId || !filename || running}
          onClick={handleRun}
        >
          {running ? '일괄 추론 실행 중...' : '일괄 추론 실행'}
        </button>
        {/* 샘플당 ~16s → 진행률 표시(무반응 오인 방지) */}
        {running && progress && (
          <span className={cx('note')}>
            {progress.done}/{progress.total} 샘플 완료
            {progress.total > progress.done &&
              ` · 남은 예상 ${Math.max(1, Math.round(((progress.total - progress.done) * 16) / 60))}분`}
          </span>
        )}
      </div>

      {result && (
        <div className={cx('results')}>
          {result.partial && (
            <p className={cx('warn')}>
              중단된 배치의 부분 결과입니다 (완료된 {result.sample_count}건만
              표시, 종합 메트릭 없음).
            </p>
          )}
          {!result.has_reference && !result.partial && (
            <p className={cx('note')}>
              데이터셋에 reference 컬럼이 없어 메트릭은 산출하지 않았습니다
              (출력만 표시).
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
                    activeMetricCols.map((col) => (
                      <th key={col.key}>{col.label}</th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {(result.samples ?? []).map((s, i) => (
                  <tr key={s.index ?? i}>
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
