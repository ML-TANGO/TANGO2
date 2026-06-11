import { useEffect, useState } from 'react';
import { useHistory, useLocation, useParams } from 'react-router-dom';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './DeploymentDetailPage.module.scss';

const cx = classNames.bind(style);

const TABS_AUTO   = ['개요', 'K8s 워커 상태'];
const TABS_MANUAL = ['개요', '배포 스크립트'];

const RUNTIMES = [
  { id: 'vllm',      name: 'vLLM',       icon: '⚡', desc: 'GPU 가속 LLM 서빙 (PagedAttention)' },
  { id: 'triton',    name: 'Triton',      icon: '🔺', desc: 'NVIDIA 다중 프레임워크 추론 서버' },
  { id: 'tgi',       name: 'TGI',         icon: '🤗', desc: 'HuggingFace Text Generation Inference' },
  { id: 'ollama',    name: 'Ollama',      icon: '🦙', desc: '로컬 LLM 간편 실행 런타임' },
  { id: 'llamacpp',  name: 'Llama.cpp',   icon: '🧩', desc: 'CPU/GGUF 기반 경량 추론 엔진' },
  { id: 'tensorrt',  name: 'TensorRT',    icon: '🚀', desc: 'NVIDIA TensorRT-LLM 최적화 엔진' },
];

const QUANT_LLAMACPP = [
  { id: 'q4_0',   label: 'Q4_0',   desc: '4-bit, 빠른 속도 / 품질 절충' },
  { id: 'q4_k_m', label: 'Q4_K_M', desc: '4-bit K-quant Medium (권장)' },
  { id: 'q5_0',   label: 'Q5_0',   desc: '5-bit, 품질 향상' },
  { id: 'q5_k_m', label: 'Q5_K_M', desc: '5-bit K-quant Medium' },
  { id: 'q8_0',   label: 'Q8_0',   desc: '8-bit, 고품질 / 용량 증가' },
  { id: 'f16',    label: 'F16',    desc: '16-bit 풀 정밀도 (비양자화)' },
];

const QUANT_GENERIC = [
  { id: 'int8',  label: 'INT8',   desc: '8-bit 정수 양자화' },
  { id: 'int4',  label: 'INT4',   desc: '4-bit 정수 양자화' },
  { id: 'fp16',  label: 'FP16',   desc: '16-bit 부동소수 (기본)' },
  { id: 'bf16',  label: 'BF16',   desc: 'BF16 부동소수 (Ampere+)' },
];

const RAG_OPTIONS = [
  { id: 'none',    label: '없음' },
  { id: 'basic',   label: '기본 RAG' },
  { id: 'advanced',label: '고급 RAG' },
];

const OPT_OPTIONS = [
  { id: 'flash_attn',   label: 'Flash Attention' },
  { id: 'cont_batch',   label: 'Continuous Batching' },
  { id: 'kv_cache',     label: 'KV Cache 최적화' },
  { id: 'tensor_para',  label: 'Tensor Parallelism' },
];

function buildScripts(dep) {
  const model = dep.built_in_model_name ?? dep.model_name ?? 'model';
  const port  = dep.url ? new URL(dep.url).port || '8000' : '8000';
  const sys   = (dep.serving_system ?? '').toLowerCase();

  if (sys.includes('vllm')) {
    return {
      docker: `docker run --gpus all -p ${port}:8000 \\\n  -v /opt/models:/models \\\n  vllm/vllm-openai:latest \\\n  --model /models/${model} \\\n  --host 0.0.0.0 --port 8000`,
      systemd: `[Unit]\nDescription=vLLM serving – ${dep.deployment_name}\n\n[Service]\nExecStart=docker run --gpus all -p ${port}:8000 \\\n  -v /opt/models:/models \\\n  vllm/vllm-openai:latest \\\n  --model /models/${model}\nRestart=always\n\n[Install]\nWantedBy=multi-user.target`,
    };
  }
  if (sys.includes('llama') || sys.includes('gguf')) {
    return {
      docker: `docker run -p ${port}:8080 \\\n  -v /opt/models:/models \\\n  ghcr.io/ggerganov/llama.cpp:server \\\n  -m /models/${model}.gguf \\\n  --host 0.0.0.0 --port 8080`,
      systemd: `[Unit]\nDescription=llama.cpp server – ${dep.deployment_name}\n\n[Service]\nExecStart=/usr/local/bin/llama-server \\\n  -m /opt/models/${model}.gguf \\\n  --host 0.0.0.0 --port ${port}\nRestart=always\n\n[Install]\nWantedBy=multi-user.target`,
    };
  }
  if (sys.includes('ollama')) {
    return {
      docker: `# 1. Ollama 서버 실행\ndocker run -d -p 11434:11434 \\\n  -v ollama-data:/root/.ollama \\\n  ollama/ollama serve\n\n# 2. 모델 등록\ndocker exec <container_id> ollama pull ${model}`,
      systemd: `[Unit]\nDescription=Ollama – ${dep.deployment_name}\n\n[Service]\nExecStart=ollama serve\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\nRestart=always\n\n[Install]\nWantedBy=multi-user.target`,
    };
  }
  if (sys.includes('tensorrt') || sys.includes('triton')) {
    return {
      docker: `docker run --gpus all -p 8000:8000 -p 8001:8001 -p 8002:8002 \\\n  -v /opt/models:/models \\\n  nvcr.io/nvidia/tritonserver:24.01-trtllm-python-py3 \\\n  tritonserver --model-repository=/models`,
      systemd: `[Unit]\nDescription=TensorRT-LLM Triton – ${dep.deployment_name}\n\n[Service]\nExecStart=docker run --gpus all -p 8000:8000 \\\n  -v /opt/models:/models \\\n  nvcr.io/nvidia/tritonserver:24.01-trtllm-python-py3 \\\n  tritonserver --model-repository=/models\nRestart=always\n\n[Install]\nWantedBy=multi-user.target`,
    };
  }
  return {
    docker:  `# 배포 스크립트를 생성하려면 서빙 시스템을 확인하세요.\n# serving_system: ${dep.serving_system ?? '미지정'}`,
    systemd: `# systemd 설정을 생성하려면 서빙 시스템을 확인하세요.`,
  };
}

export default function DeploymentDetailPage() {
  const history  = useHistory();
  const location = useLocation();
  const { did }  = useParams();
  const wid      = location.pathname.split('/')[3];

  const [dep, setDep]           = useState(null);
  const [tab, setTab]           = useState(0);
  const [copied, setCopied]     = useState('');

  // 배포 구성 상태
  const [selectedArtifact, setSelectedArtifact] = useState('');
  const [selectedRuntime,  setSelectedRuntime]  = useState('');
  const [selectedQuant,    setSelectedQuant]    = useState('');
  const [selectedRag,      setSelectedRag]      = useState('none');
  const [selectedOpts,     setSelectedOpts]     = useState([]);

  useEffect(() => {
    callApi({ url: `deployments?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const list  = Array.isArray(res.result) ? res.result : [];
        const found = list.find((d) => d.id === did);
        setDep(found ?? null);
      }
    });
  }, [wid, did]);

  const copyText = (text, key) => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(key);
    setTimeout(() => setCopied(''), 2000);
  };

  const toggleOpt = (id) =>
    setSelectedOpts((prev) => prev.includes(id) ? prev.filter((o) => o !== id) : [...prev, id]);

  if (!dep) return <div className={cx('loading')}>배포 정보를 불러오는 중...</div>;

  const isManual  = dep.deploy_method === 'manual';
  const tabs      = isManual ? TABS_MANUAL : TABS_AUTO;
  const scripts   = isManual ? buildScripts(dep) : null;
  const worker    = dep.deployment_status?.worker;
  const quantOpts = selectedRuntime === 'llamacpp' ? QUANT_LLAMACPP : QUANT_GENERIC;

  return (
    <div className={cx('page')}>
      {/* Header */}
      <div className={cx('header')}>
        <button className={cx('back-btn')} onClick={() => history.push(`/user/workspace/${wid}/deployments`)}>
          ← 목록으로
        </button>
        <div className={cx('header-info')}>
          <h1 className={cx('title')}>{dep.deployment_name}</h1>
          <div className={cx('meta-row')}>
            <span className={cx('status-badge', dep.deployment_status?.status === 'running' ? 'running' : 'stopped')}>
              {dep.deployment_status?.status === 'running' ? '● 실행 중' : '● 중지됨'}
            </span>
            {dep.target_category && (
              <span className={cx('meta-tag')}>
                {dep.target_category === 'edge-k8s' ? '⚡ 엣지' : dep.target_category === 'cloud' ? '☁️ 클라우드' : '🖥️ 독립 장치'}
              </span>
            )}
            {dep.serving_system && <span className={cx('meta-tag')}>{dep.serving_system}</span>}
            <span className={cx('method-badge', isManual ? 'manual' : 'auto')}>
              {isManual ? '📋 수동 배포' : '🔄 자동 배포'}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className={cx('tabs')}>
        {tabs.map((t, i) => (
          <button key={t} className={cx('tab', tab === i && 'active')} onClick={() => setTab(i)}>{t}</button>
        ))}
      </div>

      {/* ── Tab 0: 개요 ── */}
      {tab === 0 && (
        <div className={cx('panel')}>
          {/* 개요 정보 */}
          <div className={cx('info-table')}>
            {[
              ['배포 이름',   dep.deployment_name],
              ['모델',        dep.built_in_model_name ?? dep.model_name ?? '-'],
              ['대상 장치',   dep.target_device ?? '-'],
              ['서빙 시스템', dep.serving_system ?? dep.convert_type ?? '-'],
              ['배포 방식',   isManual ? '수동 (스크립트)' : '자동 (K8s)'],
              ['API 주소',    dep.api_address ?? dep.url ?? '-'],
              ['생성일',      dep.created_at ? dep.created_at.slice(0, 10) : '-'],
            ].map(([k, v]) => (
              <div key={k} className={cx('info-row')}>
                <span className={cx('info-key')}>{k}</span>
                <span className={cx('info-val')}>{v}</span>
              </div>
            ))}
          </div>

          {worker && (
            <div className={cx('worker-summary')}>
              {[
                ['실행 중', worker.status?.running   ?? 0, 'running'],
                ['설치 중', worker.status?.installing ?? 0, 'installing'],
                ['오류',    worker.status?.error      ?? 0, 'error'],
                ['대기',    worker.status?.pending    ?? 0, 'pending'],
              ].map(([label, cnt, cls]) => (
                <div key={cls} className={cx('worker-stat', cls)}>
                  <span className={cx('ws-count')}>{cnt}</span>
                  <span className={cx('ws-label')}>{label}</span>
                </div>
              ))}
            </div>
          )}

          {/* ── 배포 구성 ── */}
          <div className={cx('config-divider')} />

          <div className={cx('config-section')}>
            {/* 모델 아티팩트 */}
            <div className={cx('config-group')}>
              <div className={cx('config-label')}>모델 아티팩트</div>
              <select
                className={cx('artifact-select')}
                value={selectedArtifact}
                onChange={(e) => setSelectedArtifact(e.target.value)}
              >
                <option value="">아티팩트를 선택하세요</option>
                <option value="model_fp16">model_fp16.bin</option>
                <option value="model_int8">model_int8.bin</option>
                <option value="model_gguf">model.gguf (GGUF)</option>
                <option value="model_onnx">model.onnx (ONNX)</option>
                <option value="model_trt">model.plan (TensorRT)</option>
              </select>
            </div>

            {/* 서빙 런타임 */}
            <div className={cx('config-group')}>
              <div className={cx('config-label')}>서빙 런타임</div>
              <div className={cx('runtime-grid')}>
                {RUNTIMES.map((r) => (
                  <div
                    key={r.id}
                    className={cx('runtime-card', selectedRuntime === r.id && 'selected')}
                    onClick={() => { setSelectedRuntime(r.id); setSelectedQuant(''); }}
                  >
                    <span className={cx('runtime-icon')}>{r.icon}</span>
                    <span className={cx('runtime-name')}>{r.name}</span>
                    <span className={cx('runtime-desc')}>{r.desc}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 양자화 옵션 */}
            <div className={cx('config-group')}>
              <div className={cx('config-label')}>
                양자화 옵션
                <span className={cx('config-hint')}>
                  {selectedRuntime === 'llamacpp' ? '(Llama.cpp GGUF)' : selectedRuntime ? '(일반)' : ''}
                </span>
              </div>
              <div className={cx('quant-grid')}>
                {quantOpts.map((q) => (
                  <div
                    key={q.id}
                    className={cx('quant-card', selectedQuant === q.id && 'selected')}
                    onClick={() => setSelectedQuant(q.id)}
                  >
                    <div className={cx('quant-name')}>{q.label}</div>
                    <div className={cx('quant-desc')}>{q.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* RAG 적용 */}
            <div className={cx('config-group')}>
              <div className={cx('config-label')}>RAG 적용</div>
              <div className={cx('chip-row')}>
                {RAG_OPTIONS.map((r) => (
                  <div
                    key={r.id}
                    className={cx('config-chip', selectedRag === r.id && 'selected')}
                    onClick={() => setSelectedRag(r.id)}
                  >
                    {r.label}
                  </div>
                ))}
              </div>
            </div>

            {/* 최적화 옵션 */}
            <div className={cx('config-group')}>
              <div className={cx('config-label')}>최적화 옵션</div>
              <div className={cx('chip-row')}>
                {OPT_OPTIONS.map((o) => (
                  <div
                    key={o.id}
                    className={cx('config-chip', selectedOpts.includes(o.id) && 'selected')}
                    onClick={() => toggleOpt(o.id)}
                  >
                    {o.label}
                  </div>
                ))}
              </div>
            </div>

            {/* 액션 버튼 */}
            <div className={cx('action-row')}>
              <button className={cx('gen-btn', 'gen-image')}>🐳 이미지 생성</button>
              <button className={cx('gen-btn', 'gen-code')}>📋 코드 생성</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 1: K8s 워커 (auto) ── */}
      {tab === 1 && !isManual && (
        <div className={cx('panel')}>
          <h3 className={cx('section-title')}>워커 상태</h3>
          {worker ? (
            <table className={cx('worker-table')}>
              <thead>
                <tr><th>항목</th><th>값</th></tr>
              </thead>
              <tbody>
                <tr><td>총 레플리카</td><td>{worker.count}</td></tr>
                <tr><td>실행 중</td><td className={cx('ok')}>{worker.status.running}</td></tr>
                <tr><td>설치 중</td><td>{worker.status.installing}</td></tr>
                <tr><td>오류</td><td className={cx(worker.status.error > 0 ? 'err' : '')}>{worker.status.error}</td></tr>
                <tr><td>대기</td><td>{worker.status.pending}</td></tr>
                <tr><td>CPU 사용</td><td>{worker.resource_usage?.cpu} 코어</td></tr>
                <tr><td>GPU 사용</td><td>{worker.resource_usage?.gpu} 장치</td></tr>
              </tbody>
            </table>
          ) : (
            <div className={cx('empty')}>워커 정보 없음</div>
          )}
        </div>
      )}

      {/* ── Tab 1: 배포 스크립트 (manual) ── */}
      {tab === 1 && isManual && scripts && (
        <div className={cx('panel')}>
          {[
            { key: 'docker',  title: 'Docker 실행 명령어', code: scripts.docker },
            { key: 'systemd', title: 'systemd 서비스 유닛', code: scripts.systemd },
          ].map(({ key, title, code }) => (
            <div key={key} className={cx('script-block')}>
              <div className={cx('script-header')}>
                <span className={cx('script-title')}>{title}</span>
                <button className={cx('copy-btn', copied === key && 'copied')} onClick={() => copyText(code, key)}>
                  {copied === key ? '✓ 복사됨' : '복사'}
                </button>
              </div>
              <pre className={cx('code')}>{code}</pre>
            </div>
          ))}
          <div className={cx('manual-tip')}>
            💡 스크립트를 대상 장치에 복사한 후 실행하세요. <code>/opt/models</code> 경로에 모델 파일을 배치해야 합니다.
          </div>
        </div>
      )}
    </div>
  );
}
