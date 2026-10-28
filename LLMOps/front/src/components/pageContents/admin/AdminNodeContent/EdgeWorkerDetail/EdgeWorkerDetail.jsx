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

// 배포 상태별 배지 색. error 는 비동기 배포 도입으로 실제 도달 가능해졌으므로
// 회색이 아니라 경고색으로 구분한다.
const DEPLOY_STATE_TONE = {
  running: 'green',
  deploying: 'blue',
  error: 'red',
  stopped: 'gray',
};

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
            {/* deploy_stale = 배포상태를 관측한 지 오래됐거나(임계 초과) 한 번도
                관측한 적이 없다. 둘 다 "모른다" 이므로 '미상' 으로 축약한다 —
                deploy_state 가 비었다고 '미배포' 라 말하면 관측하지 않은 것을
                관측한 것처럼 주장하게 된다. */}
            {w.deploy_stale ? (
              <Badge
                size='sm'
                label={t('edge.detail.stateUnknown')}
                type='gray'
              />
            ) : w.deploy_state ? (
              <Badge
                size='sm'
                label={t(`edge.state.${w.deploy_state}`, w.deploy_state)}
                type={DEPLOY_STATE_TONE[w.deploy_state] || 'gray'}
              />
            ) : (
              '-'
            )}
          </Row>
          {/* 실패 사유는 디바이스가 /metrics 로만 알려준다. 상태만 'error' 로 보여주면
              무엇이 잘못됐는지(수신 실패·디스크 부족·docker 오류) 알 길이 없다. */}
          {!w.deploy_stale && w.deploy_state === 'error' && w.deploy_error ? (
            <Row label={t('edge.detail.deployError')}>{w.deploy_error}</Row>
          ) : null}
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
