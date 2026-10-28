import { useCallback, useEffect, useMemo, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import DeployDetailHeader from '@src/components/pageContents/llm/DeployDetail/DeployDetailHeader';
import {
  getRemoteApiConfig,
  putRemoteApiConfig,
  postPlaygroundDeployStart,
  getDetailPlayground,
} from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './RemoteApiDeploymentDetail.module.scss';

const cx = classNames.bind(style);

// provider 카드의 시각 언어는 목업(front_etri LlmJudgeEvaluationPage 의 COMMERCIAL_JUDGES)
// 을 그대로 가져왔다 — 같은 3사를 다루는 화면이 플랫폼 안에 둘 생기므로 아이콘·라벨을
// 어긋나게 두면 같은 대상이 달라 보인다. 기본 모델명은 서버가 내려주는 카탈로그를 쓰고
// (하드코딩 금지, 정본은 remote_api.provider_catalog), 여기서는 아이콘만 보탠다.
const PROVIDER_ICON = {
  chatgpt: '🟢',
  claude: '🟠',
  gemini: '🔵',
  endpoint: '🔗',
};

// 상태는 프록시 워커 **파드**에서 파생된다(get_playground_status 의 remote_api 분기) —
// '연결됨'이 아니라 '실행 중'이 맞는 말이다. installing 은 파드가 뜨는 중.
const STATE_LABEL = {
  running: { text: '실행 중', tone: 'ok' },
  installing: { text: '시작하는 중', tone: 'idle' },
  error: { text: '오류', tone: 'error' },
  stopped: { text: '중지됨', tone: 'idle' },
};

// 외부 LLM 배포 상세(deploy_type='remote_api').
//   상용 API 3사는 키만 받는다(호스트는 플랫폼이 고정 — 키가 엉뚱한 곳으로 새지 않게).
//   endpoint 는 사용자 URL 을 받고 서버가 SSRF 가드를 태운다.
//   저장하면 서버가 곧바로 도달성을 확인해 state 로 알려준다.
export default function RemoteApiDeploymentDetail() {
  const history = useHistory();
  const { params } = useRouteMatch();
  const workspaceId = params.id;
  const playgroundId = params.deployId;

  const [name, setName] = useState('');
  const [cfg, setCfg] = useState(null);
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState(null);
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);

  const selected = useMemo(
    () => providers.find((p) => p.id === provider) || null,
    [providers, provider],
  );

  const load = useCallback(async () => {
    const res = await getRemoteApiConfig(playgroundId);
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return null;
    }
    const r = res.result || {};
    setCfg(r);
    setProviders(r.providers || []);
    setProvider((prev) => prev || r.provider || null);
    if (r.model) setModel((prev) => prev || r.model);
    if (r.base_url) setBaseUrl((prev) => prev || r.base_url);
    return r;
  }, [playgroundId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([load(), getDetailPlayground(playgroundId)])
      .then(([, detail]) => {
        if (cancelled) return;
        // 상세 응답은 {info, model, model_parameter, ...} 중첩 — 이름은 info 아래다
        // (StandaloneDeploymentDetail 과 같은 규약).
        if (detail?.status === STATUS_SUCCESS)
          setName(detail.result?.info?.name || '');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load, playgroundId]);

  // provider 를 바꾸면 그 provider 의 기본 모델을 채운다(비어 있을 때만 덮어쓰지 않도록
  // 사용자가 직접 입력한 값은 유지 — 저장된 provider 로 돌아왔을 때는 저장값을 쓴다).
  const handleProvider = (id) => {
    setProvider(id);
    const meta = providers.find((p) => p.id === id);
    if (id === cfg?.provider) {
      setModel(cfg?.model || meta?.default_model || '');
      setBaseUrl(cfg?.base_url || '');
    } else {
      setModel(meta?.default_model || '');
      if (id !== 'endpoint') setBaseUrl('');
    }
  };

  const canSave =
    !!provider &&
    !saving &&
    (provider !== 'endpoint' || baseUrl.trim().length > 0) &&
    (provider === 'endpoint' || cfg?.has_key || apiKey.trim().length > 0);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await putRemoteApiConfig({
        playground_id: Number(playgroundId),
        provider,
        model: model.trim() || undefined,
        base_url: provider === 'endpoint' ? baseUrl.trim() : undefined,
        // 빈 값이면 서버가 기존 Secret 을 유지한다(모델만 바꾸는 재구성).
        api_key: apiKey.trim() || undefined,
      });
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        return;
      }
      setApiKey('');
      const r = res.result || {};
      if (r.state === 'running') toast.success('저장했습니다. 호출 가능한 구성입니다 — 시작을 눌러 워커를 띄우세요.');
      else toast.warn(`저장했습니다. 다만 연결 확인에 실패했습니다 — ${r.last_error || ''}`);
      await load();
    } finally {
      setSaving(false);
    }
  };

  // '시작' = 도달성 확인 후 프록시 워커 파드를 띄운다(helm install). 이 파드가 떠야
  // 추론·평가가 이 배포를 쓸 수 있다 — 다른 배포의 '시작'과 같은 뜻이다.
  const handleStart = async () => {
    setStarting(true);
    try {
      // 자원 필드는 서버 DTO 가 전부 기본 0 이고 remote_api 분기는 자원 경로에 들어가지도
      // 않는다 → playground_id 만 보낸다.
      const res = await postPlaygroundDeployStart({
        playground_id: Number(playgroundId),
      });
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
      } else {
        toast.success('워커가 시작되었습니다.');
      }
      await load();
    } finally {
      setStarting(false);
    }
  };

  const stateMeta = STATE_LABEL[cfg?.state] || { text: '미구성', tone: 'idle' };

  return (
    <div className={cx('remote-cont')}>
      <DeployDetailHeader
        title={name || '외부 LLM 배포'}
        onBack={() => history.push(`/user/workspace/${workspaceId}/llmplayground`)}
        right={<span className={cx('type-chip')}>외부 LLM</span>}
      />

      {loading ? (
        <div className={cx('loading')}>불러오는 중…</div>
      ) : (
        <div className={cx('body')}>
          <section className={cx('panel')}>
            <div className={cx('panel-head')}>
              <h3>제공자</h3>
              <span className={cx('state-chip', stateMeta.tone)}>{stateMeta.text}</span>
            </div>
            <p className={cx('hint')}>
              상용 API 는 호출 주소를 플랫폼이 고정합니다 — 입력하는 것은 키뿐입니다.
            </p>
            <div className={cx('provider-grid')}>
              {providers.map((p) => (
                <button
                  key={p.id}
                  type='button'
                  className={cx('provider-card', provider === p.id && 'selected')}
                  aria-pressed={provider === p.id}
                  onClick={() => handleProvider(p.id)}
                >
                  <span className={cx('provider-icon')}>{PROVIDER_ICON[p.id]}</span>
                  <span className={cx('provider-label')}>{p.label}</span>
                  {p.default_model && (
                    <span className={cx('provider-model')}>{p.default_model}</span>
                  )}
                </button>
              ))}
            </div>
          </section>

          {provider && (
            <section className={cx('panel')}>
              <h3>연결 설정</h3>
              <div className={cx('field')}>
                <label htmlFor='ra-model'>모델</label>
                <input
                  id='ra-model'
                  value={model}
                  placeholder={selected?.default_model || '모델명'}
                  onChange={(e) => setModel(e.target.value)}
                />
              </div>

              {selected?.requires_url && (
                <div className={cx('field')}>
                  <label htmlFor='ra-url'>엔드포인트 URL</label>
                  <input
                    id='ra-url'
                    value={baseUrl}
                    placeholder='http://host:8000/v1'
                    onChange={(e) => setBaseUrl(e.target.value)}
                  />
                  <span className={cx('field-hint')}>
                    OpenAI 호환 주소. 내부망 주소도 쓸 수 있지만 메타데이터 주소는 차단됩니다.
                  </span>
                </div>
              )}

              <div className={cx('field')}>
                <label htmlFor='ra-key'>
                  API 키{selected?.requires_url ? ' (선택)' : ''}
                </label>
                <input
                  id='ra-key'
                  type='password'
                  value={apiKey}
                  autoComplete='new-password'
                  placeholder={cfg?.has_key ? '저장된 키 사용 중 — 바꿀 때만 입력' : 'API 키'}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <span className={cx('field-hint')}>
                  키는 화면·목록·응답 어디에도 다시 표시되지 않습니다.
                </span>
              </div>

              {cfg?.state === 'error' && cfg?.last_error && (
                <div className={cx('error-box')}>{cfg.last_error}</div>
              )}

              <div className={cx('actions')}>
                <ButtonV2 disabled={!canSave} onClick={handleSave}>
                  {saving ? '저장 중…' : '저장'}
                </ButtonV2>
                <ButtonV2
                  colorType='white'
                  disabled={!cfg?.provider || starting}
                  onClick={handleStart}
                >
                  {starting ? '시작하는 중…' : '시작'}
                </ButtonV2>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
