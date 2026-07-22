import { useTranslation } from 'react-i18next';

import { Badge } from '@jonathan/ui-react';

// 엣지 워커 행 확장 상세. AdminNodeDetail(K8s 전용)과 분리 — 엣지 워커 객체(_worker_view)를
// 받아 연결/자원/배포/토큰/최근 heartbeat 를 표시. 값이 없으면 '-'.

const fmtBytes = (n) => {
  if (!n || n <= 0) return '-';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), u.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
};

const dash = (v) => (v === null || v === undefined || v === '' ? '-' : v);

const rowStyle = {
  display: 'flex',
  padding: '6px 0',
  borderBottom: '1px solid rgba(0,0,0,0.06)',
};
const labelStyle = { width: 150, color: '#6b7280', flexShrink: 0 };
const valueStyle = { flex: 1, wordBreak: 'break-all' };

const Row = ({ label, children }) => (
  <div style={rowStyle}>
    <div style={labelStyle}>{label}</div>
    <div style={valueStyle}>{children}</div>
  </div>
);

const Section = ({ title, children }) => (
  <div style={{ marginBottom: 16 }}>
    <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
    {children}
  </div>
);

const EdgeWorkerDetail = ({ worker }) => {
  const { t } = useTranslation();
  const w = worker || {};

  const online = w.conn_status === 'online';

  let heartbeat = null;
  try {
    heartbeat = w.last_heartbeat_json ? JSON.parse(w.last_heartbeat_json) : null;
  } catch (e) {
    heartbeat = null;
  }

  return (
    <div style={{ padding: '16px 24px', fontSize: 13 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(280px, 1fr))',
          gap: 24,
        }}
      >
        <Section title={t('edge.detail.connection')}>
          <Row label={t('edge.field.deviceId')}>
            <code>{dash(w.device_id)}</code>
          </Row>
          <Row label={t('edge.field.name')}>{dash(w.name)}</Row>
          <Row label={t('edge.field.track')}>{dash(w.device_type)}</Row>
          <Row label={t('status.label')}>
            <Badge
              size='sm'
              label={online ? 'online' : 'offline'}
              type={online ? 'primary-2' : 'gray'}
            />
          </Row>
          <Row label={t('edge.col.lastSeen')}>{dash(w.last_seen)}</Row>
          <Row label={t('edge.field.remoteManager')}>
            {dash(w.remote_manager_url)}
          </Row>
        </Section>

        <Section title={t('edge.col.resource')}>
          <Row label='CPU'>{w.cpu_cores ? `${w.cpu_cores} cores` : '-'}</Row>
          <Row label='RAM'>{fmtBytes(w.mem_total)}</Row>
          <Row label='GPU'>{dash(w.gpu_info)}</Row>
          <Row label={t('edge.detail.containers')}>
            {dash(w.container_count)}
          </Row>
        </Section>

        <Section title={t('edge.col.deploy')}>
          <Row label={t('model.label')}>{dash(w.deploy_model)}</Row>
          <Row label='Version'>{dash(w.deploy_version)}</Row>
          <Row label='State'>
            {w.deploy_state ? (
              <Badge
                size='sm'
                label={w.deploy_state}
                type={w.deploy_state === 'running' ? 'green' : 'gray'}
              />
            ) : (
              '-'
            )}
          </Row>
        </Section>

        <Section title={t('edge.detail.token')}>
          <Row label={t('edge.token.prefix')}>{dash(w.token_prefix)}</Row>
          <Row label={t('edge.token.expires')}>{dash(w.token_expires_at)}</Row>
        </Section>
      </div>

      {heartbeat && (
        <Section title={t('edge.detail.lastHeartbeat')}>
          <pre
            style={{
              background: 'rgba(0,0,0,0.04)',
              padding: 12,
              borderRadius: 6,
              overflow: 'auto',
              maxHeight: 220,
              margin: 0,
            }}
          >
            {JSON.stringify(heartbeat, null, 2)}
          </pre>
        </Section>
      )}
    </div>
  );
};

export default EdgeWorkerDetail;
