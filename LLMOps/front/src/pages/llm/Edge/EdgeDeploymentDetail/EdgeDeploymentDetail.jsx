import { useCallback, useEffect, useMemo, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import Tab from '@src/components/molecules/Tab';
import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import PlaygroundAdvancedOptions from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundAdvancedOptions';
import {
  deployEdgeWorker,
  getEdgeWorkers,
  refreshEdgeWorker,
} from '@src/apis/flightbase/edge';
import { getModel, getQuantizeLineage } from '@src/apis/llm/model';
import { getDetailPlayground } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './EdgeDeploymentDetail.module.scss';

const cx = classNames.bind(style);

// 런타임 엔진 기본 6종(+ 커스텀 도커 이미지 pull). 엔진별 기본 서빙 이미지(목업).
//   커스텀 선택 시 사용자가 이미지 경로를 직접 입력해 pull.
const ENGINES = [
  { id: 'vllm', label: 'vLLM', image: 'docker.io/acrylaaai/llm_deployment:dev' },
  { id: 'llama_cpp', label: 'llama.cpp', image: 'docker.io/acrylaaai/llm_deployment_llamacpp:dev' },
  { id: 'tgi', label: 'TGI', image: 'docker.io/acrylaaai/llm_deployment_tgi:dev' },
  { id: 'ollama', label: 'Ollama', image: 'docker.io/acrylaaai/llm_deployment_ollama:dev' },
  { id: 'triton', label: 'Triton', image: 'docker.io/acrylaaai/llm_deployment_triton:dev' },
  { id: 'tensorrt', label: 'TensorRT', image: 'docker.io/acrylaaai/llm_deployment_tensorrt:dev' },
];
const CUSTOM_ENGINE = 'custom';
const DEFAULT_EDGE_IMAGE = ENGINES[1].image; // llama.cpp (엣지 기본)

// 파라미터 기본값(목업 — 배포 요청 body 확장 시 사용).
const DEFAULT_PARAMS = { temperature: 1, top_p: 0.9, top_k: 50, max_new_tokens: 512 };
const PARAM_META = [
  { key: 'temperature', label: 'Temperature', min: 0, max: 2, step: 0.1 },
  { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.05 },
  { key: 'top_k', label: 'Top K', min: 0, max: 100, step: 1 },
  { key: 'max_new_tokens', label: 'Max Sequence', min: 1, max: 4096, step: 1 },
];

function Row({ k, v }) {
  return (
    <div className={cx('row')}>
      <span className={cx('k')}>{k}</span>
      <span className={cx('v')}>{v}</span>
    </div>
  );
}

// 사용자용 온디바이스(엣지) 배포 상세 — 3탭(정보/배포/모니터링), Playground 셸 미러.
//   정보: 디바이스 정보 + 현재 배포 요약.
//   배포: [모델(런타임엔진 6+커스텀 → 모델선택 → 양자화 GGUF → 모델정보)] | 파라미터 | 고급옵션
//         | [디바이스 정보(디바이스 선택) + 현재 배포 상태(배포 실행)].
//   모니터링: /metrics 폴링 + heartbeat 자원/상태.
export default function EdgeDeploymentDetail() {
  const history = useHistory();
  const match = useRouteMatch();
  // deployId = 배포(playground row, deploy_type='edge') id. 배포 대상 디바이스는 아래 targetId 로 별도 선택.
  const { id: workspaceId, deployId } = match.params;

  const [workers, setWorkers] = useState([]);
  const [targetId, setTargetId] = useState(''); // 배포 대상 디바이스 — '배포' 탭 드롭다운에서 선택
  const [worker, setWorker] = useState(null);
  const [project, setProject] = useState(null); // 배포 프로젝트 메타(정보 탭)
  const [tab, setTab] = useState('INFO');

  // 배포 폼 상태
  const [engine, setEngine] = useState('llama_cpp');
  const [image, setImage] = useState(DEFAULT_EDGE_IMAGE); // 커스텀 도커 이미지 경로
  const [models, setModels] = useState([]);
  const [modelId, setModelId] = useState('');
  const [lineage, setLineage] = useState([]);
  const [lineageId, setLineageId] = useState('');
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [deploying, setDeploying] = useState(false);

  const isCustomEngine = engine === CUSTOM_ENGINE;

  // 전체 디바이스 목록 — 마운트 시 1회(+배포 후 명시 갱신). targetId 변경마다 재fetch 하지 않음(레이스/과다호출 방지).
  const loadWorkers = useCallback(async () => {
    const { status, result } = await getEdgeWorkers();
    setWorkers(status === STATUS_SUCCESS && Array.isArray(result) ? result : []);
  }, []);

  useEffect(() => {
    loadWorkers();
  }, [loadWorkers]);

  // 선택 디바이스(worker) = 로드된 목록에서 targetId 로 derive(네트워크 없음). 모니터링 폴링이 live 로 갱신.
  useEffect(() => {
    setWorker(workers.find((x) => String(x.id) === String(targetId)) || null);
  }, [workers, targetId]);

  // 배포 프로젝트 메타 — playground 상세 조회('new' 생성 진입 시 미조회). 응답은 {info,...} 중첩.
  useEffect(() => {
    if (!deployId || deployId === 'new') return undefined;
    let alive = true;
    (async () => {
      const { status, result } = await getDetailPlayground(deployId);
      if (alive && status === STATUS_SUCCESS) setProject(result?.info || null);
    })();
    return () => {
      alive = false;
    };
  }, [deployId]);

  // 배포 폼용 모델 목록
  useEffect(() => {
    let alive = true;
    (async () => {
      const { status, result } = await getModel(workspaceId);
      if (alive && status === STATUS_SUCCESS) setModels(result || []);
    })();
    return () => {
      alive = false;
    };
  }, [workspaceId]);

  // 모델 선택 시 완료된 양자화 산출물(lineage) 로드 (모델>양자화 기능 이관)
  useEffect(() => {
    if (!modelId) {
      setLineage([]);
      setLineageId('');
      return undefined;
    }
    let alive = true;
    (async () => {
      const { status, result } = await getQuantizeLineage(modelId);
      if (alive && status === STATUS_SUCCESS) {
        setLineage((result?.lineage || []).filter((l) => l.status === 'completed'));
      }
    })();
    return () => {
      alive = false;
    };
  }, [modelId]);

  // 모니터링 탭에서만 refresh 폴링(마운트 기준 → 탭 떠나면 정지)
  useEffect(() => {
    if (tab !== 'MONITOR' || !targetId) return undefined; // 디바이스 미선택('new') 시 폴링 안 함
    let alive = true;
    const tick = async () => {
      const { status, result } = await refreshEdgeWorker(targetId);
      if (alive && status === STATUS_SUCCESS) setWorker(result);
    };
    tick();
    const iv = setInterval(tick, 10000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, [tab, targetId]);

  const selectedModel = models.find((m) => String(m.id) === String(modelId));
  const selectedLineage = lineage.find((l) => String(l.id) === String(lineageId));

  const handleSelectEngine = (id) => {
    setEngine(id);
    const eng = ENGINES.find((e) => e.id === id);
    if (eng) setImage(eng.image); // 기본 엔진 → 기본 이미지. 커스텀은 입력 유지.
  };

  const handleParam = (key, value) => setParams((p) => ({ ...p, [key]: +value }));

  const handleDeploy = async () => {
    if (!worker) return toast.error('디바이스를 선택하세요.');
    if (!selectedLineage) return toast.error('양자화 모델을 선택하세요.');
    if (!image) return toast.error('런타임 이미지를 확인하세요.');
    setDeploying(true);
    const { status, message } = await deployEdgeWorker(targetId, {
      image,
      model_name: selectedModel?.name,
      model_version: selectedLineage.quantization_type,
      gguf_path: selectedLineage.gguf_path,
    });
    setDeploying(false);
    if (status === STATUS_SUCCESS) {
      toast.success('배포를 요청했습니다.');
      loadWorkers();
    } else {
      toast.error(message || '배포에 실패했습니다.');
    }
  };

  const heartbeat = useMemo(() => {
    try {
      return worker?.last_heartbeat_json ? JSON.parse(worker.last_heartbeat_json) : null;
    } catch {
      return null;
    }
  }, [worker]);

  const isOnline = worker?.conn_status === 'online';
  const tabOptions = [
    { label: 'information.label', value: 'INFO' },
    { label: '배포', value: 'DEPLOY' },
    { label: 'Monitoring', value: 'MONITOR' },
  ];

  return (
    <div className={cx('playground-cont')}>
      <DeployDetailHeader
        title={project?.name || '온디바이스 배포'}
        onBack={() => history.push(`/user/workspace/${workspaceId}/llmplayground`)}
        right={
          <>
            <span className={cx('type-chip', 'edge')}>온디바이스</span>
            {worker && (
              <span className={cx('conn', isOnline ? 'on' : 'off')}>
                {worker.conn_status}
              </span>
            )}
          </>
        }
      />

      <div className={cx('tab-bar')}>
        <Tab
          type='c'
          sidePaddingNone
          option={tabOptions}
          select={{ value: tab }}
          tabHandler={({ value }) => setTab(value)}
        />
      </div>

      {/* ── 정보 (배포 프로젝트 설정 정보 — Playground 정보 탭과 동형) ── */}
      {tab === 'INFO' && (
        <div className={cx('content-cont')}>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>정보</h3>
            <div className={cx('info-field')}>
              <span className={cx('label')}>설명</span>
              <p className={cx('info-value')}>{project?.description || '-'}</p>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>배포 유형</span>
              <span className={cx('info-value')}>온디바이스 (엣지)</span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>공개 범위</span>
              <span className={cx('info-value')}>
                {project?.access ? 'Public' : 'Private'}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>소유자</span>
              <span className={cx('info-value')}>{project?.owner || '-'}</span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>생성 일시</span>
              <span className={cx('info-value')}>{project?.create_datetime || '-'}</span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>최근 업데이트</span>
              <span className={cx('info-value')}>{project?.update_datetime || '-'}</span>
            </div>
          </section>
        </div>
      )}

      {/* ── 배포 ── */}
      {tab === 'DEPLOY' && (
        <div className={cx('deploy-cont')}>
          {/* 1열: 런타임 엔진 + 모델 선택/정보 */}
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>모델 · 런타임</h3>

            <span className={cx('label')} id='edge-engine-label'>런타임 엔진</span>
            <div className={cx('engine-grid')} role='radiogroup' aria-labelledby='edge-engine-label'>
              {ENGINES.map((eng) => (
                <button
                  key={eng.id}
                  type='button'
                  role='radio'
                  aria-checked={engine === eng.id}
                  className={cx('engine-opt', engine === eng.id && 'selected')}
                  onClick={() => handleSelectEngine(eng.id)}
                >
                  {eng.label}
                </button>
              ))}
              <button
                type='button'
                role='radio'
                aria-checked={isCustomEngine}
                className={cx('engine-opt', 'custom', isCustomEngine && 'selected')}
                onClick={() => handleSelectEngine(CUSTOM_ENGINE)}
              >
                커스텀 이미지
              </button>
            </div>

            <label className={cx('label')} htmlFor='edge-image'>
              {isCustomEngine ? '커스텀 도커 이미지 (pull)' : '런타임 이미지'}
            </label>
            <input
              id='edge-image'
              className={cx('input')}
              value={image}
              onChange={(e) => setImage(e.target.value)}
              placeholder='docker.io/org/image:tag'
              readOnly={!isCustomEngine}
            />

            <div className={cx('divider')} />

            <label className={cx('label')} htmlFor='edge-model'>모델</label>
            <select
              id='edge-model'
              className={cx('select')}
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              <option value=''>모델 선택</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>

            <label className={cx('label')} htmlFor='edge-gguf'>양자화 모델(GGUF)</label>
            <select
              id='edge-gguf'
              className={cx('select')}
              value={lineageId}
              onChange={(e) => setLineageId(e.target.value)}
              disabled={!modelId}
            >
              <option value=''>{modelId ? '양자화 산출물 선택' : '모델 먼저 선택'}</option>
              {lineage.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.quantization_type} · {l.gguf_path?.split('/').pop()}
                </option>
              ))}
            </select>

            {selectedModel && (
              <>
                <div className={cx('divider')} />
                <span className={cx('sub-title')}>모델 정보</span>
                <Row k='이름' v={selectedModel.name || '-'} />
                <Row k='양자화' v={selectedLineage?.quantization_type || '-'} />
                <Row k='GGUF' v={selectedLineage?.gguf_path?.split('/').pop() || '-'} />
              </>
            )}
          </section>

          {/* 2열: 파라미터 */}
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>파라미터 설정</h3>
            {PARAM_META.map((p) => (
              <div key={p.key} className={cx('param')}>
                <div className={cx('param-head')}>
                  <span className={cx('label')}>{p.label}</span>
                  <span className={cx('param-val')}>{params[p.key]}</span>
                </div>
                <input
                  type='range'
                  className={cx('slider')}
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  value={params[p.key]}
                  onChange={(e) => handleParam(p.key, e.target.value)}
                />
              </div>
            ))}
          </section>

          {/* 3열: 고급 옵션(공용 placeholder 재사용) */}
          <PlaygroundAdvancedOptions />

          {/* 4열: 디바이스 정보(선택) + 현재 배포 상태 */}
          <div className={cx('stacked-col')}>
            <section className={cx('card')}>
              <h3 className={cx('card-title')}>디바이스 정보</h3>
              <label className={cx('label')} htmlFor='edge-device'>엣지 디바이스</label>
              <select
                id='edge-device'
                className={cx('select')}
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
              >
                {workers.length === 0 && <option value={targetId}>디바이스 없음</option>}
                {workers.map((w) => (
                  <option key={w.id} value={String(w.id)}>
                    {w.name || w.device_id} {w.conn_status ? `(${w.conn_status})` : ''}
                  </option>
                ))}
              </select>
              <Row k='유형' v={worker?.device_type || '-'} />
              <Row k='연결' v={worker?.conn_status || '-'} />
              <Row k='자원' v={`CPU ${worker?.cpu_cores ?? '-'} / ${worker?.gpu_info || 'GPU -'}`} />
            </section>

            <section className={cx('card')}>
              <h3 className={cx('card-title')}>현재 배포 상태</h3>
              <Row k='상태' v={worker?.deploy_state || '미배포'} />
              <Row k='로드 모델' v={worker?.deploy_model || heartbeat?.model_loaded || '-'} />
              <Row k='최근 확인' v={worker?.last_seen || '-'} />
              <ButtonV2
                label={deploying ? '배포 중…' : '배포 실행'}
                colorType='skyblue'
                disabled={deploying || !isOnline}
                onClick={handleDeploy}
                style={{ width: '100%', marginTop: '8px' }}
              />
              {!isOnline && (
                <p className={cx('hint')}>디바이스가 online일 때 배포할 수 있습니다.</p>
              )}
            </section>
          </div>
        </div>
      )}

      {/* ── 모니터링 ── */}
      {tab === 'MONITOR' && (
        <div className={cx('grid', 'monitor-grid')}>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>자원 / 상태</h3>
            <Row k='연결' v={worker?.conn_status || '-'} />
            <Row k='배포 상태' v={worker?.deploy_state || '-'} />
            <Row k='CPU 코어' v={worker?.cpu_cores ?? '-'} />
            <Row k='메모리(GB)' v={worker?.mem_total ?? '-'} />
            <Row k='GPU' v={worker?.gpu_info || '-'} />
            <Row k='컨테이너 수' v={worker?.container_count ?? '-'} />
          </section>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>Heartbeat</h3>
            <Row k='최근 확인' v={worker?.last_seen || '-'} />
            {heartbeat ? (
              <>
                <Row k='CPU %' v={heartbeat.cpu_pct ?? '-'} />
                <Row k='GPU %' v={heartbeat.gpu_pct ?? '-'} />
                <Row k='로드 모델' v={heartbeat.model_loaded || '-'} />
                <Row k='추론 수' v={heartbeat.inference_count_total ?? '-'} />
              </>
            ) : (
              <p className={cx('hint')}>heartbeat 수신 대기 중…</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
