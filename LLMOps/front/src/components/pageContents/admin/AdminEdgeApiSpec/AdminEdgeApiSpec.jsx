import { useHistory } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import { copyToClipboardWithToast } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AdminEdgeApiSpec.module.scss';

const cx = classNames.bind(style);

const NODES_PATH = '/admin/nodes';

// 기관 디바이스가 호출 (Edge → Cloud). 스키마는 기술 규약이라 리터럴 유지.
// ⚠️ 이 상수들은 실제 구현(apps/fb_resource/src/edge, apps/edge_remote_manager)과
//    examples/edge-agent/README.md 의 계약 v1 을 그대로 옮긴 것이다. 셋이 어긋나면
//    기관이 구현한 에이전트가 연동에 실패한다 — 계약을 바꾸면 세 곳을 함께 고칠 것.
const EDGE_TO_CLOUD = [
  {
    method: 'post',
    path: '{platform}/api/edge/devices/{device_id}/heartbeat',
    descKey: 'edgeApi.heartbeat.desc',
    schema: `{
  "timestamp": ISO8601,
  "cpu_pct": float,            // 0~100
  "gpu_pct": float,            // 0~100
  "gpu_mem_gb": float,
  "gpu_mem_used_gb": float,
  "disk_gb": float,
  "disk_used_gb": float,
  "model_loaded": string | null,
  "inference_count_total": int,
  "inference_latency_p50_ms": float,
  "inference_latency_p99_ms": float,
  "last_error": string | null
}
// Header: Authorization: Bearer {device_token}
// 200 정상 · 401 토큰 오류 · 429 최소 간격(30초) 미만`,
  },
  {
    method: 'get',
    path: '{platform}/api/edge/devices/{device_id}/artifact',
    descKey: 'edgeApi.artifact.desc',
    schema: `// Header: Authorization: Bearer {device_token}   // heartbeat 와 같은 토큰
// Header: Range: bytes={받은 바이트}-            // 이어받기(선택)
// HEAD 도 같은 인증으로 지원 — Content-Length 로 크기만 확인

200 / 206  파일 바이트 (Accept-Ranges: bytes)
401        토큰 없음 · 불일치 · 만료
404        이 디바이스에 인가된 아티팩트 없음
416        Range 가 파일 크기를 넘음
429        디바이스별 전송량 한도 초과 — 잠시 후 재시도`,
  },
];

// 기관 디바이스가 노출 의무 (Cloud → Edge, 플랫폼이 호출).
const CLOUD_TO_EDGE = [
  {
    method: 'post',
    path: '{remote_manager_url}/ops',
    descKey: 'edgeApi.ops.desc',
    schema: `// Header: Authorization: Bearer {ops_token}   // 설정 시 검증 의무
//   회전 중에는 직전 키(OPS_TOKEN_PREV)도 허용해야 한다 — 무중단 교체(계약 1.1)
// 배포
{ "op":"deploy", "image": string, "model": string, "version": string,
  "gguf_path": string,        // 저장할 파일명 (lineage-<id>-<이름>.gguf)
  "model_url": string,        // 이 URL 에서 모델을 받아온 뒤 기동
  "params": { "port": int, "env": {}, "docker_args": [], "cmd": [] } }
  → 202 {"status":"deploying","contract_version":"1.1"}   // model_url 있음: 즉시 응답 후 백그라운드
  → 200 {"status":"running","contract_version":"1.1"}     // model_url 없음: 동기 처리
  → 409 {"status":"error","detail":"deploy already in progress"}
  →     {"status":"error","detail": string}               // 실패는 반드시 error 로

// 중지 — 진행 중인 비동기 배포도 함께 무효화하고 last_deploy_error 를 해제할 것
{ "op":"stop" }
  → {"status":"stopped","contract_version":"1.1"}
  →  {"status":"error","detail": string}`,
  },
  {
    method: 'get',
    path: '{remote_manager_url}/metrics',
    descKey: 'edgeApi.metrics.desc',
    schema: `// Header: Authorization: Bearer {ops_token}
{
  "contract_version": "1.1",
  "deploy_in_progress": bool,      // 비동기 배포 진행 중
  "last_deploy_error": string|null,// 직전 비동기 배포 실패 사유(성공 시 null)
  "containers": [
    { "name": string, "image": string, "state": "running"|"stopped",
      "model": string, "version": string }
  ],
  "container_count": int,
  "node_cpu_total": int,           // 코어 수
  "memory_total": int,             // GB
  "gpu": string                    // 없으면 "none"
}`,
  },
];

const SECURITY_KEYS = [
  'edgeApi.security.tokens',
  'edgeApi.security.opsToken',
  'edgeApi.security.transport',
  'edgeApi.security.rate',
  'edgeApi.security.filename',
  'edgeApi.security.network',
  'edgeApi.security.contract',
];

// 기관 발송용 OpenAPI 3.0 (요약). 규약 변경 빈도 낮아 FE 번들 정적 문자열로 유지(P3, spec §7).
const OPENAPI_YAML = `openapi: 3.0.3
info:
  title: GenAI Platform Edge Device API
  version: "1.1"
  description: >-
    Edge device integration contract v1 — device pushes heartbeat and pulls the
    model artifact; the platform drives deployment through the device agent.
paths:
  /api/edge/devices/{device_id}/heartbeat:
    post:
      summary: Resource/status heartbeat (device -> platform, >= 30s apart)
      security: [{ deviceToken: [] }]
      parameters:
        - { name: device_id, in: path, required: true, schema: { type: string } }
      responses:
        "200": { description: accepted }
        "401": { description: invalid or expired token }
        "429": { description: sent sooner than the 30s minimum }
  /api/edge/devices/{device_id}/artifact:
    get:
      summary: Download the model artifact authorized for this device
      security: [{ deviceToken: [] }]
      parameters:
        - { name: device_id, in: path, required: true, schema: { type: string } }
        - { name: Range, in: header, required: false, schema: { type: string } }
      responses:
        "200": { description: full file }
        "206": { description: partial content (resume) }
        "401": { description: invalid or expired token }
        "404": { description: no artifact authorized for this device }
        "416": { description: range beyond end of file }
        "429": { description: per-device transfer budget exceeded }
    head:
      summary: Artifact size probe (Content-Length)
      security: [{ deviceToken: [] }]
      responses:
        "200": { description: headers only }
        "401": { description: invalid or expired token }
        "404": { description: no artifact authorized for this device }
        "429": { description: per-device transfer budget exceeded }
  "{remote_manager_url}/ops":
    post:
      summary: Deploy or stop a container (platform -> device)
      security: [{ opsToken: [] }]
      responses:
        "200": { description: running (synchronous deploy) }
        "202": { description: deploying (model_url given, running in background) }
        "409": { description: a deploy is already in progress }
  "{remote_manager_url}/metrics":
    get:
      summary: Real container state and node resources (platform -> device)
      security: [{ opsToken: [] }]
      responses: { "200": { description: metrics } }
components:
  securitySchemes:
    deviceToken: { type: http, scheme: bearer, description: per-device token issued by the platform }
    opsToken: { type: http, scheme: bearer, description: shared token proving the caller is the platform (previous key also accepted during rotation) }
`;

/**
 * Edge 측 API 규격 뷰어 (admin, 정적). SP-8 확장 / 수용계획서 3.1.
 * 아크릴은 규격만 제공 — 기관이 본인 디바이스에 맞춰 구현. OpenAPI 복사/다운로드 제공.
 */
const AdminEdgeApiSpec = () => {
  const { t } = useTranslation();
  const history = useHistory();

  const downloadYaml = () => {
    const blob = new Blob([OPENAPI_YAML], { type: 'text/yaml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'edge-api-v1.yaml';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const renderEndpoint = (e) => (
    <div key={`${e.method}-${e.path}`} className={cx('endpoint')}>
      <div className={cx('endpoint-head')}>
        <span className={cx('method', e.method)}>{e.method.toUpperCase()}</span>
        <span className={cx('url')}>{e.path}</span>
      </div>
      <div className={cx('endpoint-desc')}>{t(e.descKey)}</div>
      <pre className={cx('schema')}>{e.schema}</pre>
    </div>
  );

  return (
    <div>
      <PageHeader
        title={t('edgeApi.title')}
        rightComponent={
          <div className={cx('head-actions')}>
            <ButtonV2
              type='outline'
              size='s'
              label={t('edgeApi.copyYaml')}
              onClick={() => copyToClipboardWithToast(OPENAPI_YAML)}
            />
            <ButtonV2
              type='outline'
              size='s'
              label={t('edgeApi.downloadYaml')}
              onClick={downloadYaml}
            />
            <ButtonV2
              type='outline'
              size='s'
              label={t('edgeApi.pdf')}
              onClick={() => window.print()}
            />
            <ButtonV2
              size='s'
              label={t('edgeApi.back')}
              onClick={() => history.push(NODES_PATH)}
            />
          </div>
        }
      />
      <div className={cx('spec')}>
        <div className={cx('version')}>{t('edgeApi.version')}</div>
        <div className={cx('desc')}>{t('edgeApi.desc')}</div>

        {/* 책임 분담 */}
        <div className={cx('card')}>
          <div className={cx('card-title')}>
            {t('edgeApi.responsibility.title')}
          </div>
          <table className={cx('resp-table')}>
            <tbody>
              <tr>
                <td className={cx('rk')}>
                  {t('edgeApi.responsibility.acryl')}
                </td>
                <td>{t('edgeApi.responsibility.acrylDesc')}</td>
              </tr>
              <tr>
                <td className={cx('rk', 'org')}>
                  {t('edgeApi.responsibility.org')}
                </td>
                <td>{t('edgeApi.responsibility.orgDesc')}</td>
              </tr>
              <tr>
                <td className={cx('rk')}>{t('edgeApi.responsibility.comm')}</td>
                <td>{t('edgeApi.responsibility.commDesc')}</td>
              </tr>
              <tr>
                <td className={cx('rk')}>{t('edgeApi.responsibility.auth')}</td>
                <td>{t('edgeApi.responsibility.authDesc')}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Edge → Cloud */}
        <div className={cx('card')}>
          <div className={cx('card-title')}>{t('edgeApi.e2c.title')}</div>
          <div className={cx('card-desc')}>{t('edgeApi.e2c.desc')}</div>
          {EDGE_TO_CLOUD.map(renderEndpoint)}
        </div>

        {/* Cloud → Edge */}
        <div className={cx('card')}>
          <div className={cx('card-title')}>{t('edgeApi.c2e.title')}</div>
          <div className={cx('card-desc')}>{t('edgeApi.c2e.desc')}</div>
          {CLOUD_TO_EDGE.map(renderEndpoint)}
        </div>

        {/* 보안 / 운영 */}
        <div className={cx('card')}>
          <div className={cx('card-title')}>{t('edgeApi.security.title')}</div>
          <ul className={cx('sec-list')}>
            {SECURITY_KEYS.map((k) => (
              <li key={k}>{t(k)}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default AdminEdgeApiSpec;
