import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useSelector } from 'react-redux';
import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import {
  Badge,
  ButtonV2,
  Checkbox,
  Radio,
  Selectbox,
} from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
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
import style from './BatchInference.module.scss';

const cx = classNames.bind(style);

// 데이터셋 일괄 추론(WBS 4.3 배치, 목업 InferenceDetailPage 배치모드 포팅) — 단독·이중 공용.
//   데이터셋 선택 → 파일 → 샘플 수 → 메트릭 → 일괄 실행 → 결과(요약+표).
//   모드는 BE 가 세션에서 판별한다(GET /playgrounds/batch/sse → resolve_dual_prompt_gen):
//   이중이면 샘플마다 LLM1→LLM2 체인(추론 2N), 단독이면 데이터셋 프롬프트로 바로 추론(N).
//   FE 는 같은 화면·같은 스트림 규약을 쓰고 isDual 은 호출량 안내 문구에만 쓴다.
//   메트릭은 BE 인-프로세스 BLEU/ROUGE(자체메트릭). 샘플 수 상한 10(실체 부여:
//   목업 [10,50,100,500]→[3,5,10]). SPICE/METEOR/CIDEr(목업)는 벤치 컨테이너 전용→미노출.
//   UI 는 플랫폼 조나단 규약 — 설정=카드 1장(라벨은 InputBoxWithLabel), 선택 컨트롤은
//   데이터셋/파일=Selectbox(개수 가변·Radio 의 ul 은 flex 라 줄바꿈 불가), 샘플 수=Radio,
//   메트릭=Checkbox. 진행률/결과 표는 xlib 에 대응 컴포넌트(Progress·Table)가 없어 커스텀 유지.
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
const SAMPLE_OPTIONS = SAMPLE_COUNTS.map((n) => ({
  label: `${n}개`,
  value: n,
  disabled: false,
}));

// 외부 SDS(VLM) 배치 — 이미지/AIS 는 데이터셋 행(image·ais_rows)에서 per-sample 로 읽는다.
//   ⚠️ 출력 유형을 UI 로 노출하지 않는 이유(2026-07-27 클러스터 실측, playground 38 / dataset 7):
//   현재 배포된 eva-vlm-backend 는 텍스트 프롬프트에 전혀 반응하지 않는다 — custom_prompt 를
//   바꿔도, custom_prompt 를 빼고 output_type(컨테이너 PROMPT_MAP)만 바꿔도 출력이 바이트 단위
//   동일했다(배선은 client→BFF→adapter→container→모델입력 4계층 모두 정상 확인). 즉 선택을
//   노출하면 아무 효과 없는 컨트롤이 된다. 컨테이너가 프롬프트에 반응하게 되면 이 상수를
//   Selectbox(OUTPUT_TYPE_OPTIONS)로 바꾸고 데이터셋 정답 유형과 맞추도록 안내할 것.
const SDS_BATCH_OUTPUT_TYPE = '간결 항해조력메시지';

// Selectbox 는 폭을 스스로 잡지 않으므로 폼 컨트롤 폭을 명시(플랫폼 선례와 동일 패턴).
const SELECT_STYLE = {
  selectboxForm: { width: '100%' },
  listForm: { width: '100%' },
};

const BatchInference = ({ playgroundId, isExternal = false, isDual = false }) => {
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

  // Selectbox 는 {label,value} 리스트 규약 → 원본을 변형하지 않고 표시용으로만 파생.
  const datasetOptions = useMemo(
    () => datasets.map((d) => ({ label: d.name, value: d.id })),
    [datasets],
  );
  const fileOptions = useMemo(
    () => files.map((f) => ({ label: f.file_name, value: f.file_name })),
    [files],
  );
  const selectedDataset =
    datasetOptions.find((o) => String(o.value) === String(datasetId)) ?? null;
  const selectedFile = fileOptions.find((o) => o.value === filename) ?? null;

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
    // 외부 SDS: 출력 유형만 전달(이미지/AIS 는 데이터셋 행에서 per-sample 로 읽음).
    if (isExternal) params.set('output_type', SDS_BATCH_OUTPUT_TYPE);

    const es = new EventSourcePolyfill(
      `${API_HOST}playgrounds/batch/sse?${params.toString()}`,
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
      <section className={cx('card')}>
        <div className={cx('card-head')}>
          <h3 className={cx('card-title')}>일괄 추론 설정</h3>
          {isExternal && <Badge type='gray' size='sm' label='SDS · VLM' />}
        </div>

        {isExternal && (
          <p className={cx('note')}>
            SDS(VLM) 추론은 샘플별 이미지·AIS가 필요합니다. 데이터셋 각 행에
            image(데이터셋 내 상대경로)와 ais_rows(자선 my_ship=1 포함)를 포함해
            주세요. AIS 필드가 없으면 프롬프트의 [선박 AIS 정보] 텍스트에서
            복원합니다.
          </p>
        )}

        {datasets.length === 0 ? (
          <EmptyBox
            isBox
            customStyle={{ height: '120px' }}
            text='사용 가능한 데이터셋이 없습니다.'
          />
        ) : (
          <div className={cx('form-row')}>
            <InputBoxWithLabel
              labelText='데이터셋'
              labelSize='large'
              disableErrorMsg
            >
              <Selectbox
                list={datasetOptions}
                selectedItem={selectedDataset}
                placeholder='데이터셋을 선택하세요'
                onChange={(item) => handleDatasetSelect(item.value)}
                customStyle={SELECT_STYLE}
              />
            </InputBoxWithLabel>

            {/* 데이터셋 안의 파일 선택 — 1개여도 노출(어떤 파일로 추론하는지 명시) */}
            <InputBoxWithLabel
              labelText='파일'
              labelSize='large'
              disableErrorMsg
            >
              <Selectbox
                list={fileOptions}
                selectedItem={selectedFile}
                placeholder={
                  datasetId ? '파일을 선택하세요' : '데이터셋을 먼저 선택하세요'
                }
                isDisable={fileOptions.length === 0}
                onChange={(item) => setFilename(item.value)}
                customStyle={SELECT_STYLE}
              />
            </InputBoxWithLabel>
          </div>
        )}

        <InputBoxWithLabel
          labelText='샘플 수'
          labelSize='large'
          disableErrorMsg
        >
          <Radio
            name='batch-sample-count'
            options={SAMPLE_OPTIONS}
            selectedValue={sampleCount}
            onChange={(e) => setSampleCount(Number(e.currentTarget.value))}
          />
        </InputBoxWithLabel>
        <p className={cx('note')}>
          {isDual
            ? '샘플당 프롬프트 생성 → 추론 2회를 호출하므로 최대 10개까지 지원합니다.'
            : '샘플당 추론 1회를 호출합니다. 동기 배치라 최대 10개까지 지원합니다.'}
        </p>

        <InputBoxWithLabel
          labelText='정량 메트릭'
          optionalText='reference 필요'
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <div className={cx('check-row')}>
            {METRICS.map((m) => (
              <Checkbox
                key={m.id}
                label={m.label}
                checked={selectedMetrics.includes(m.id)}
                onChange={() => toggleMetric(m.id)}
              />
            ))}
          </div>
        </InputBoxWithLabel>
      </section>

      <div className={cx('run-row')}>
        {/* 샘플당 ~16s → 진행률 표시(무반응 오인 방지). xlib 에 Progress 컴포넌트 없음 → 텍스트. */}
        {running && progress && (
          <span className={cx('progress')}>
            {progress.done}/{progress.total} 샘플 완료
            {progress.total > progress.done &&
              ` · 남은 예상 ${Math.max(1, Math.round(((progress.total - progress.done) * 16) / 60))}분`}
          </span>
        )}
        <ButtonV2
          type='solid'
          colorType='blue'
          size='l'
          label={running ? '일괄 추론 중' : '일괄 추론 실행'}
          isLoading={running}
          disabled={!datasetId || !filename || running}
          onClick={handleRun}
        />
      </div>

      {result && (
        <section className={cx('card')}>
          <div className={cx('card-head')}>
            <h3 className={cx('card-title')}>추론 결과</h3>
            <Badge
              type={result.partial ? 'yellow' : 'blue'}
              size='sm'
              label={`${result.sample_count ?? (result.samples ?? []).length}건`}
            />
          </div>

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
              <span className={cx('summary-title')}>종합 결과 (평균)</span>
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
        </section>
      )}
    </div>
  );
};

export default BatchInference;
