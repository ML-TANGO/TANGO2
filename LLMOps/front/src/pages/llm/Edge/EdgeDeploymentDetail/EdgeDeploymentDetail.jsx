import { useCallback, useEffect, useMemo, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import Tab from '@src/components/molecules/Tab';
import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import {
  deployEdgeWorker,
  getEdgeWorkers,
  stopEdgeWorker,
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
  {
    id: 'vllm',
    label: 'vLLM',
    image: 'docker.io/acrylaaai/llm_deployment:dev',
  },
  {
    id: 'llama_cpp',
    label: 'llama.cpp',
    image: 'docker.io/acrylaaai/llm_deployment_llamacpp:dev',
  },
  {
    id: 'tgi',
    label: 'TGI',
    image: 'docker.io/acrylaaai/llm_deployment_tgi:dev',
  },
  {
    id: 'ollama',
    label: 'Ollama',
    image: 'docker.io/acrylaaai/llm_deployment_ollama:dev',
  },
  {
    id: 'triton',
    label: 'Triton',
    image: 'docker.io/acrylaaai/llm_deployment_triton:dev',
  },
  {
    id: 'tensorrt',
    label: 'TensorRT',
    image: 'docker.io/acrylaaai/llm_deployment_tensorrt:dev',
  },
];
const CUSTOM_ENGINE = 'custom';
const DEFAULT_EDGE_IMAGE = ENGINES[1].image; // llama.cpp (엣지 기본)

// 파라미터 기본값(목업 — 배포 요청 body 확장 시 사용).
const DEFAULT_PARAMS = {
  temperature: 1,
  top_p: 0.9,
  top_k: 50,
  max_new_tokens: 512,
};
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
//   배포: [모델(런타임엔진 6+커스텀 → 모델선택 → 양자화 GGUF → 모델정보)] | 파라미터
//         | [디바이스 정보(디바이스 선택) + 현재 배포 상태(배포 실행)].
//   모니터링: /metrics 폴링 + heartbeat 자원/상태.
export default function EdgeDeploymentDetail() {
  const { t } = useTranslation();
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
  const [stopping, setStopping] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const isCustomEngine = engine === CUSTOM_ENGINE;

  // 전체 디바이스 목록 — 마운트 시 1회(+배포 후 명시 갱신). targetId 변경마다 재fetch 하지 않음(레이스/과다호출 방지).
  const loadWorkers = useCallback(async () => {
    const { status, result } = await getEdgeWorkers();
    setWorkers(
      status === STATUS_SUCCESS && Array.isArray(result) ? result : [],
    );
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
        setLineage(
          (result?.lineage || []).filter((l) => l.status === 'completed'),
        );
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
  const selectedLineage = lineage.find(
    (l) => String(l.id) === String(lineageId),
  );

  const handleSelectEngine = (id) => {
    setEngine(id);
    const eng = ENGINES.find((e) => e.id === id);
    if (eng) setImage(eng.image); // 기본 엔진 → 기본 이미지. 커스텀은 입력 유지.
  };

  const handleParam = (key, value) =>
    setParams((p) => ({ ...p, [key]: +value }));

  const handleDeploy = async () => {
    if (!worker) return toast.error(t('edge.toast.selectDevice'));
    if (!selectedLineage) return toast.error(t('edge.toast.selectQuantModel'));
    if (!image) return toast.error(t('edge.toast.checkImage'));
    setDeploying(true);
    const { status, message } = await deployEdgeWorker(targetId, {
      image,
      model_name: selectedModel?.name,
      model_version: selectedLineage.quantization_type,
      gguf_path: selectedLineage.gguf_path,
    });
    setDeploying(false);
    if (status === STATUS_SUCCESS) {
      toast.success(t('edge.toast.deployRequested'));
      loadWorkers();
    } else {
      toast.error(message || t('edgeDeploy.toast.fail'));
    }
  };

  // 목록 GET 만으로는 부족하다: BE `_worker_view` 는 heartbeat 토큰이 있는 워커만
  // last_seen staleness 로 conn_status 를 파생하고, pull-only 워커(remote_manager_url
  // 만 있음)는 **저장된** conn_status 를 그대로 돌려준다(주기 폴러 부재). 그 값은
  // POST /refresh 가 /metrics 를 찍어야 갱신되므로, 선택된 디바이스가 있으면 먼저
  // refresh 를 돌린 뒤 목록을 다시 받는다. 하필 canOperate 가 겨냥하는 게 그 워커군이다.
  const handleRefresh = async () => {
    setRefreshing(true);
    if (targetId) {
      // 실패를 삼키지 않는다 — 화면이 그대로면 사용자는 "정상(오프라인)" 인지
      // "요청 자체가 실패" 인지 구분할 수 없다. handleStop 과 대칭을 맞춘다.
      const res = await refreshEdgeWorker(targetId);
      if (res.status !== STATUS_SUCCESS) {
        toast.error(res.message || t('edge.toast.refreshFail'));
      }
    }
    await loadWorkers();
    setRefreshing(false);
  };

  const handleStop = async () => {
    if (!worker) return toast.error(t('edge.toast.selectDevice'));
    setStopping(true);
    const { status, message } = await stopEdgeWorker(targetId);
    setStopping(false);
    if (status === STATUS_SUCCESS) {
      toast.success(t('edge.toast.stopRequested'));
      loadWorkers();
    } else {
      toast.error(message || t('edge.toast.stopFail'));
    }
  };

  const heartbeat = useMemo(() => {
    try {
      return worker?.last_heartbeat_json
        ? JSON.parse(worker.last_heartbeat_json)
        : null;
    } catch {
      return null;
    }
  }, [worker]);

  const isOnline = worker?.conn_status === 'online';
  // online 은 heartbeat(디바이스→플랫폼) 판정이고, 실행·중지는 remote_manager_url 로
  // 가는 반대 방향이다. 그 주소는 선택 입력이라(heartbeat-only 디바이스 허용) online
  // 인데도 /ops 를 보낼 수 없는 조합이 존재한다 — 그 경우 버튼을 열어두면 누를 때마다
  // "unsafe or invalid remote_manager_url" 로 실패한다. 두 조건을 함께 본다.
  //
  // 존재 여부만 보면 부족하다: BE `_safe_rm_url` 은 스킴·userinfo·path/query/fragment·
  // loopback 을 거절하므로 `http://127.0.0.1` 이나 경로가 붙은 URL 은 저장돼 있어도
  // 매번 서버에서 거절된다. 같은 규칙을 여기서 미리 걸러 "누를 수 있는데 항상 실패"
  // 를 없앤다(서버가 정본이고 이건 UI 예측이다).
  const hasRemoteUrl = useMemo(() => {
    const raw = worker?.remote_manager_url;
    if (!raw) return false;
    try {
      const u = new URL(raw);
      if (!['http:', 'https:'].includes(u.protocol)) return false;
      if (u.username || u.password || u.search || u.hash) return false;
      if (u.pathname && u.pathname !== '/') return false;
      // WHATWG URL 은 IPv6 를 브래킷째 준다 — `new URL('http://[::1]').hostname`
      // === '[::1]'. 문자열 배열 비교로는 잡히지 않는다(실측 확인).
      const host = u.hostname.replace(/^\[|\]$/g, '').toLowerCase();
      if (host === 'localhost' || host === '::1' || host === '::') return false;
      // BE `_safe_rm_url` 은 해석된 IP 가 loopback/link-local/multicast/unspecified/
      // reserved 인지 본다. 여기서 대역을 맞춘다 — 문자열 하나만 막았을 때
      // 127.0.0.2 · 169.254.169.254(메타데이터) · 224.0.0.1 이 전부 통과했다.
      const m = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
      if (m) {
        const a = Number(m[1]);
        const b = Number(m[2]);
        if (a === 127 || a === 0) return false; // loopback 127/8 · unspecified 0/8
        if (a === 169 && b === 254) return false; // link-local (메타데이터 SSRF 타깃)
        if (a >= 224) return false; // multicast 224/4 + reserved 240/4
      }
      // DNS 이름이 위 대역으로 해석되는 경우는 브라우저가 판정할 수 없다 — 서버가
      // 정본이고 이건 "누를 수 있는데 항상 실패" 를 줄이는 UI 예측이다.
      return true;
    } catch {
      return false;
    }
  }, [worker]);
  const canOperate = isOnline && hasRemoteUrl;
  // deploy 가 202(async)를 받으면 deploy_state 는 deploying 으로 남는다. 그 상태를
  // 중지 대상에서 빼면 끊긴 배포를 끌 수단이 없어지고("중지할 배포가 없습니다" 라는
  // 거짓 안내까지 붙는다) 워커를 지워도 디바이스에 컨테이너가 유령으로 남는다 —
  // 이 기능이 없애려던 문제가 바로 그 구간에서 재현된다. BE 삭제 게이트도 동일 집합.
  // error 도 포함한다 — deploy 실패는 "컨테이너가 없다" 는 보장이 아니다(이미지 pull
  // 실패 후 Created/crash-loop 컨테이너가 남을 수 있고, agent 도 docker 불가 시 기존
  // 컨테이너를 건드리지 않고 error 를 준다). BE stop_edge_worker 는 deploy_state 를
  // 아예 검사하지 않으므로, FE 가 여기서 막으면 정리 경로가 UI 에서 사라진다.
  const stoppable = ['running', 'deploying', 'error'].includes(
    worker?.deploy_state,
  );
  const tabOptions = [
    { label: 'information.label', value: 'INFO' },
    { label: 'deployment.label', value: 'DEPLOY' },
    { label: 'Monitoring', value: 'MONITOR' },
  ];

  return (
    <div className={cx('playground-cont')}>
      <DeployDetailHeader
        title={project?.name || t('edge.detail.title')}
        onBack={() =>
          history.push(`/user/workspace/${workspaceId}/llmplayground`)
        }
        right={
          <>
            <span className={cx('type-chip', 'edge')}>
              {t('edge.detail.onDevice')}
            </span>
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
            <h3 className={cx('card-title')}>{t('information.label')}</h3>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('description.label')}</span>
              <p className={cx('info-value')}>{project?.description || '-'}</p>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('deploymentType.label')}</span>
              <span className={cx('info-value')}>
                {t('deploymentTarget.edge.label')}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('releaseType.label')}</span>
              <span className={cx('info-value')}>
                {project?.access ? 'Public' : 'Private'}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('owner.label')}</span>
              <span className={cx('info-value')}>{project?.owner || '-'}</span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>{t('createdAt.label')}</span>
              <span className={cx('info-value')}>
                {project?.create_datetime || '-'}
              </span>
            </div>
            <div className={cx('info-field')}>
              <span className={cx('label')}>
                {t('deployDetail.info.lastUpdated')}
              </span>
              <span className={cx('info-value')}>
                {project?.update_datetime || '-'}
              </span>
            </div>
          </section>
        </div>
      )}

      {/* ── 배포 ── */}
      {tab === 'DEPLOY' && (
        <div className={cx('deploy-cont')}>
          {/* 1열: 런타임 엔진 + 모델 선택/정보 */}
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>
              {t('deployDetail.section.modelRuntime')}
            </h3>

            <span className={cx('label')} id='edge-engine-label'>
              {t('deployDetail.field.engine')}
            </span>
            <div
              className={cx('engine-grid')}
              role='radiogroup'
              aria-labelledby='edge-engine-label'
            >
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
                className={cx(
                  'engine-opt',
                  'custom',
                  isCustomEngine && 'selected',
                )}
                onClick={() => handleSelectEngine(CUSTOM_ENGINE)}
              >
                {t('deployDetail.engine.custom')}
              </button>
            </div>

            <label className={cx('label')} htmlFor='edge-image'>
              {isCustomEngine
                ? t('deployDetail.field.customImage')
                : t('deployDetail.field.runtimeImage')}
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

            <label className={cx('label')} htmlFor='edge-model'>
              {t('model.label')}
            </label>
            <select
              id='edge-model'
              className={cx('select')}
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              <option value=''>{t('deployDetail.model.select')}</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>

            <label className={cx('label')} htmlFor='edge-gguf'>
              {t('deployDetail.field.ggufModel')}
            </label>
            <select
              id='edge-gguf'
              className={cx('select')}
              value={lineageId}
              onChange={(e) => setLineageId(e.target.value)}
              disabled={!modelId}
            >
              <option value=''>
                {modelId
                  ? t('deployDetail.gguf.select')
                  : t('deployDetail.gguf.selectModelFirst')}
              </option>
              {lineage.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.quantization_type} · {l.gguf_path?.split('/').pop()}
                </option>
              ))}
            </select>

            {selectedModel && (
              <>
                <div className={cx('divider')} />
                <span className={cx('sub-title')}>
                  {t('deployDetail.section.modelInfo')}
                </span>
                <Row k={t('name.label')} v={selectedModel.name || '-'} />
                <Row
                  k={t('deployDetail.row.quantization')}
                  v={selectedLineage?.quantization_type || '-'}
                />
                <Row
                  k='GGUF'
                  v={selectedLineage?.gguf_path?.split('/').pop() || '-'}
                />
              </>
            )}
          </section>

          {/* 2열: 파라미터 */}
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>{t('parameterSettings.label')}</h3>
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

          {/* 3열: 디바이스 정보(선택) + 현재 배포 상태 */}
          <div className={cx('stacked-col')}>
            <section className={cx('card')}>
              <h3 className={cx('card-title')}>
                {t('edge.detail.deviceInfo')}
              </h3>
              <label className={cx('label')} htmlFor='edge-device'>
                {t('edge.field.device')}
              </label>
              <select
                id='edge-device'
                className={cx('select')}
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
              >
                {/* placeholder 는 워커가 있든 없든 항상 렌더한다. 없으면 targetId 초기값('')이
                    어떤 option 과도 매칭되지 않아 브라우저가 첫 워커를 '표시만' 하고 state 는
                    빈 문자열로 남는다 → worker undefined → isOnline false → '배포 실행' 이
                    영구 비활성. 게다가 디바이스가 1개면 같은 항목을 다시 골라도 값이 바뀌지
                    않아 change 이벤트가 안 나므로 사용자가 복구할 수 없다(2026-09-11 실측). */}
                <option value=''>
                  {workers.length === 0
                    ? t('edge.field.device.none')
                    : t('edge.field.device.select')}
                </option>
                {workers.map((w) => (
                  <option key={w.id} value={String(w.id)}>
                    {w.name || w.device_id}{' '}
                    {w.conn_status ? `(${w.conn_status})` : ''}
                  </option>
                ))}
              </select>
              {/* 목록은 마운트 시 1회만 받으므로 뒤늦게 online 이 된 디바이스가 반영되지
                  않는다. 모니터링 탭은 refreshEdgeWorker 를 폴링하지만 이 탭에는 갱신 수단이
                  없었다 — 여기서 명시적으로 다시 받는다. */}
              <ButtonV2
                type='outline'
                size='s'
                label={t('edge.action.refresh')}
                onClick={handleRefresh}
                // refresh 가 stop 직전의 running metrics 를 읽고 stop 의 DB 갱신
                // 뒤에 기록하면 제거된 컨테이너가 다시 running 으로 표시된다.
                // 배포·중지 버튼도 refreshing 을 보므로 양방향으로 막힌다.
                disabled={refreshing || deploying || stopping}
                style={{ marginTop: '4px' }}
              />
              <Row k={t('type.label')} v={worker?.device_type || '-'} />
              <Row
                k={t('edge.detail.connection')}
                v={worker?.conn_status || '-'}
              />
              <Row
                k={t('resource.label')}
                v={`CPU ${worker?.cpu_cores ?? '-'} / ${worker?.gpu_info || 'GPU -'}`}
              />
            </section>

            <section className={cx('card')}>
              <h3 className={cx('card-title')}>
                {t('edge.detail.currentDeploy')}
              </h3>
              <Row
                k={t('status.label')}
                v={worker?.deploy_state || t('edge.detail.notDeployed')}
              />
              {/* `''` 는 stop·refresh 가 "배포 없음" 을 **명시적으로** 새긴 값이고
                  null/undefined 는 "정보 없음" 이다. 둘을 falsy 로 뭉개면 빈 문자열이
                  heartbeat 폴백으로 새고, last_heartbeat_json 은 디바이스가 마지막에
                  push 한 원본이라 다음 heartbeat(~35초)까지 옛 모델명이 계속 보인다 —
                  "배포 필드를 비운다" 는 수정이 이 화면에서 무효화되던 지점이다. */}
              <Row
                k={t('edge.detail.loadedModel')}
                v={
                  worker?.deploy_model != null
                    ? worker.deploy_model || '-'
                    : heartbeat?.model_loaded || '-'
                }
              />
              <Row k={t('edge.detail.lastSeen')} v={worker?.last_seen || '-'} />
              <ButtonV2
                label={
                  deploying
                    ? t('edge.detail.deploying')
                    : t('edge.detail.runDeploy')
                }
                colorType='skyblue'
                disabled={deploying || stopping || refreshing || !canOperate}
                onClick={handleDeploy}
                style={{ width: '100%', marginTop: '8px' }}
              />
              <ButtonV2
                type='outline'
                label={
                  stopping
                    ? t('edge.detail.stopping')
                    : t('edge.detail.stopDeploy')
                }
                disabled={
                  deploying ||
                  stopping ||
                  refreshing ||
                  !canOperate ||
                  !stoppable
                }
                onClick={handleStop}
                style={{ width: '100%', marginTop: '6px' }}
              />
              {/* 비활성 사유를 분기해 보여준다. 같은 회색 버튼에 원인이 여러 개면
                  사용자가 무엇을 고쳐야 하는지 알 수 없다. online 은 heartbeat
                  (디바이스→플랫폼) 판정이고 실행·중지는 remote_manager_url 로 가는
                  반대 방향이라, online 이어도 조작이 불가능한 조합이 존재한다. */}
              {!worker && (
                <p className={cx('hint')}>{t('edge.detail.selectFirst')}</p>
              )}
              {worker && !isOnline && (
                <p className={cx('hint')}>{t('edge.detail.onlineOnly')}</p>
              )}
              {worker && isOnline && !hasRemoteUrl && (
                <p className={cx('hint')}>{t('edge.detail.noRemoteUrl')}</p>
              )}
              {canOperate && !stoppable && (
                <p className={cx('hint')}>{t('edge.detail.nothingToStop')}</p>
              )}
            </section>
          </div>
        </div>
      )}

      {/* ── 모니터링 ── */}
      {tab === 'MONITOR' && (
        <div className={cx('grid', 'monitor-grid')}>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>
              {t('edge.monitor.resourceStatus')}
            </h3>
            <Row
              k={t('edge.detail.connection')}
              v={worker?.conn_status || '-'}
            />
            <Row
              k={t('edge.monitor.deployStatus')}
              v={worker?.deploy_state || '-'}
            />
            <Row k={t('cpuCores.label')} v={worker?.cpu_cores ?? '-'} />
            <Row k={t('edge.monitor.memory')} v={worker?.mem_total ?? '-'} />
            <Row k={t('gpu.label')} v={worker?.gpu_info || '-'} />
            <Row
              k={t('edge.monitor.containers')}
              v={worker?.container_count ?? '-'}
            />
          </section>
          <section className={cx('card')}>
            <h3 className={cx('card-title')}>Heartbeat</h3>
            <Row k={t('edge.detail.lastSeen')} v={worker?.last_seen || '-'} />
            {heartbeat ? (
              <>
                <Row k='CPU %' v={heartbeat.cpu_pct ?? '-'} />
                <Row k='GPU %' v={heartbeat.gpu_pct ?? '-'} />
                <Row
                  k={t('edge.detail.loadedModel')}
                  v={heartbeat.model_loaded || '-'}
                />
                <Row
                  k={t('edge.monitor.inferenceCount')}
                  v={heartbeat.inference_count_total ?? '-'}
                />
              </>
            ) : (
              <p className={cx('hint')}>{t('edge.monitor.heartbeatWaiting')}</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
