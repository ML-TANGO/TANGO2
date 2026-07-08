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
const EDGE_TO_CLOUD = [
  {
    method: 'post',
    path: 'https://api.gaip.acryl.ai/edge/devices/{device_id}/heartbeat',
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
// Header: Authorization: Bearer {edge_token}`,
  },
  {
    method: 'post',
    path: 'https://api.gaip.acryl.ai/edge/{node_id}/inference-event',
    descKey: 'edgeApi.inferenceEvent.desc',
    schema: `{
  "request_id": uuid,
  "model_id": string,
  "latency_ms": float,
  "input_tokens": int,
  "output_tokens": int,
  "status": "ok" | "error" | "timeout"
}`,
  },
];

// 기관 디바이스가 노출 의무 (Cloud → Edge, Playground/플랫폼이 호출).
const CLOUD_TO_EDGE = [
  {
    method: 'post',
    path: '{edge_endpoint}/inference',
    descKey: 'edgeApi.inference.desc',
    schema: `// Request
{ "image": base64 string, "prompt": string,
  "max_tokens": int (default 512), "temperature": float (default 0.7) }
// Response
{ "response": string, "latency_ms": float, "tokens_per_sec": float }`,
  },
  {
    method: 'get',
    path: '{edge_endpoint}/health',
    descKey: 'edgeApi.health.desc',
    schema: `{ "status": "healthy" | "degraded" | "unhealthy",
  "model_loaded": string, "uptime_sec": int, "version": string }`,
  },
  {
    method: 'put',
    path: '{edge_endpoint}/model',
    descKey: 'edgeApi.otaModel.desc',
    schema: `{ "model_id": string,
  "download_url": string,          // registry.jonathan.acryl.ai/...
  "checksum": sha256,
  "rollback_on_failure": bool (default true) }`,
  },
];

const SECURITY_KEYS = [
  'edgeApi.security.tls',
  'edgeApi.security.token',
  'edgeApi.security.rate',
  'edgeApi.security.checksum',
  'edgeApi.security.network',
  'edgeApi.security.logs',
];

// 기관 발송용 OpenAPI 3.0 (요약). 규약 변경 빈도 낮아 FE 번들 정적 문자열로 유지(P3, spec §7).
const OPENAPI_YAML = `openapi: 3.0.3
info:
  title: GenAI Platform Edge Device API
  version: "1.0"
  description: Edge device integration contract (heartbeat push + inference/health/OTA).
servers:
  - url: https://api.gaip.acryl.ai
paths:
  /edge/devices/{device_id}/heartbeat:
    post:
      summary: Resource/status heartbeat (device -> cloud, every 30s)
      security: [{ bearerAuth: [] }]
      parameters:
        - { name: device_id, in: path, required: true, schema: { type: string } }
      responses: { "200": { description: accepted }, "401": { description: invalid token } }
  /edge/{node_id}/inference-event:
    post:
      summary: Inference event log (optional)
      security: [{ bearerAuth: [] }]
  "{edge_endpoint}/inference":
    post: { summary: "Inference (cloud -> edge, institution-hosted)" }
  "{edge_endpoint}/health":
    get: { summary: "Health check (cloud -> edge)" }
  "{edge_endpoint}/model":
    put: { summary: "OTA model replace (cloud -> edge, sha256 verified)" }
components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer }
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
