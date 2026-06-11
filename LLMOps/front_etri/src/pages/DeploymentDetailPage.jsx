import { useEffect, useState } from 'react';
import { useHistory, useLocation, useParams } from 'react-router-dom';
import { callApi, STATUS_SUCCESS } from '@src/network';
import classNames from 'classnames/bind';
import style from './DeploymentDetailPage.module.scss';

const cx = classNames.bind(style);

const TABS_AUTO   = ['개요', 'K8s 워커 상태', 'API 테스트'];
const TABS_MANUAL = ['개요', '배포 스크립트', 'API 테스트'];

function buildScripts(dep) {
  const model  = dep.built_in_model_name ?? dep.model_name ?? 'model';
  const port   = dep.url ? new URL(dep.url).port || '8000' : '8000';
  const sys    = (dep.serving_system ?? '').toLowerCase();

  if (sys.includes('vllm')) {
    return {
      docker: `docker run --gpus all -p ${port}:8000 \\
  -v /opt/models:/models \\
  vllm/vllm-openai:latest \\
  --model /models/${model} \\
  --host 0.0.0.0 --port 8000`,
      systemd: `[Unit]
Description=vLLM serving – ${dep.deployment_name}

[Service]
ExecStart=docker run --gpus all -p ${port}:8000 \\
  -v /opt/models:/models \\
  vllm/vllm-openai:latest \\
  --model /models/${model}
Restart=always

[Install]
WantedBy=multi-user.target`,
    };
  }
  if (sys.includes('llama') || sys.includes('gguf')) {
    return {
      docker: `docker run -p ${port}:8080 \\
  -v /opt/models:/models \\
  ghcr.io/ggerganov/llama.cpp:server \\
  -m /models/${model}.gguf \\
  --host 0.0.0.0 --port 8080`,
      systemd: `[Unit]
Description=llama.cpp server – ${dep.deployment_name}

[Service]
ExecStart=/usr/local/bin/llama-server \\
  -m /opt/models/${model}.gguf \\
  --host 0.0.0.0 --port ${port}
Restart=always

[Install]
WantedBy=multi-user.target`,
    };
  }
  if (sys.includes('ollama')) {
    return {
      docker: `# 1. Ollama 서버 실행
docker run -d -p 11434:11434 \\
  -v ollama-data:/root/.ollama \\
  ollama/ollama serve

# 2. 모델 등록
docker exec <container_id> ollama pull ${model}`,
      systemd: `[Unit]
Description=Ollama – ${dep.deployment_name}

[Service]
ExecStart=ollama serve
Environment="OLLAMA_HOST=0.0.0.0:11434"
Restart=always

[Install]
WantedBy=multi-user.target`,
    };
  }
  if (sys.includes('tensorrt') || sys.includes('triton')) {
    return {
      docker: `docker run --gpus all -p 8000:8000 -p 8001:8001 -p 8002:8002 \\
  -v /opt/models:/models \\
  nvcr.io/nvidia/tritonserver:24.01-trtllm-python-py3 \\
  tritonserver --model-repository=/models`,
      systemd: `[Unit]
Description=TensorRT-LLM Triton – ${dep.deployment_name}

[Service]
ExecStart=docker run --gpus all -p 8000:8000 \\
  -v /opt/models:/models \\
  nvcr.io/nvidia/tritonserver:24.01-trtllm-python-py3 \\
  tritonserver --model-repository=/models
Restart=always

[Install]
WantedBy=multi-user.target`,
    };
  }
  return {
    docker: `# 배포 스크립트를 생성하려면 서빙 시스템을 확인하세요.\n# serving_system: ${dep.serving_system ?? '미지정'}`,
    systemd: `# systemd 설정을 생성하려면 서빙 시스템을 확인하세요.`,
  };
}

export default function DeploymentDetailPage() {
  const history  = useHistory();
  const location = useLocation();
  const { did }  = useParams();
  const wid      = location.pathname.split('/')[3];

  const [dep, setDep]       = useState(null);
  const [tab, setTab]       = useState(0);
  const [copied, setCopied] = useState('');
  const [apiUrl, setApiUrl] = useState('');
  const [apiBody, setApiBody]   = useState('{"prompt": "테스트 입력"}');
  const [apiResult, setApiResult] = useState(null);
  const [apiLoading, setApiLoading] = useState(false);

  useEffect(() => {
    callApi({ url: `deployments?workspace_id=${wid}`, method: 'GET' }).then((res) => {
      if (res.status === STATUS_SUCCESS) {
        const list = Array.isArray(res.result) ? res.result : [];
        const found = list.find((d) => d.id === did);
        setDep(found ?? null);
        if (found) setApiUrl(found.api_address ?? found.url ?? '');
      }
    });
  }, [wid, did]);

  const copyText = (text, key) => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(key);
    setTimeout(() => setCopied(''), 2000);
  };

  const runApiTest = () => {
    setApiLoading(true);
    setApiResult(null);
    setTimeout(() => {
      setApiResult({
        status: 200,
        body: JSON.stringify({ id: 'mock-resp', choices: [{ text: '모의 응답입니다.' }], usage: { total_tokens: 42 } }, null, 2),
        latency: (Math.random() * 0.5 + 0.1).toFixed(2),
      });
      setApiLoading(false);
    }, 1200);
  };

  if (!dep) return <div className={cx('loading')}>배포 정보를 불러오는 중...</div>;

  const isManual = dep.deploy_method === 'manual';
  const tabs     = isManual ? TABS_MANUAL : TABS_AUTO;
  const scripts  = isManual ? buildScripts(dep) : null;
  const worker   = dep.deployment_status?.worker;

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

          {/* Worker summary */}
          {worker && (
            <div className={cx('worker-summary')}>
              {[
                ['실행 중', worker.status?.running ?? 0, 'running'],
                ['설치 중', worker.status?.installing ?? 0, 'installing'],
                ['오류',    worker.status?.error ?? 0, 'error'],
                ['대기',    worker.status?.pending ?? 0, 'pending'],
              ].map(([label, cnt, cls]) => (
                <div key={cls} className={cx('worker-stat', cls)}>
                  <span className={cx('ws-count')}>{cnt}</span>
                  <span className={cx('ws-label')}>{label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab 1: K8s 워커 (auto) / 배포 스크립트 (manual) ── */}
      {tab === 1 && !isManual && (
        <div className={cx('panel')}>
          <h3 className={cx('section-title')}>워커 상태</h3>
          {worker ? (
            <table className={cx('worker-table')}>
              <thead>
                <tr>
                  <th>항목</th><th>값</th>
                </tr>
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

      {/* ── Tab 2: API 테스트 ── */}
      {tab === 2 && (
        <div className={cx('panel')}>
          <div className={cx('api-form')}>
            <div className={cx('field')}>
              <label className={cx('field-label')}>엔드포인트 URL</label>
              <input
                className={cx('api-input')}
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder='http://...'
              />
            </div>
            <div className={cx('field')}>
              <label className={cx('field-label')}>요청 본문 (JSON)</label>
              <textarea
                className={cx('api-textarea')}
                rows={5}
                value={apiBody}
                onChange={(e) => setApiBody(e.target.value)}
              />
            </div>
            <div className={cx('run-row')}>
              <button className={cx('run-btn', apiLoading && 'disabled')} disabled={apiLoading} onClick={runApiTest}>
                {apiLoading ? '요청 중...' : '테스트 실행'}
              </button>
            </div>
            {apiResult && (
              <div className={cx('api-result')}>
                <div className={cx('api-result-header')}>
                  <span className={cx('ok')}>HTTP {apiResult.status}</span>
                  <span className={cx('api-latency')}>{apiResult.latency}s</span>
                </div>
                <pre className={cx('code')}>{apiResult.body}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
