import { useCallback, useEffect, useRef, useState } from 'react';
import { useHistory } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';
import { STATUS_SUCCESS } from '@src/network';
import {
  deleteEdgeLabel,
  deleteEdgeWorker,
  getEdgeWorkers,
  refreshEdgeWorker,
  upsertEdgeLabel,
} from '@src/apis/flightbase/edge';

import classNames from 'classnames/bind';
import style from './EdgeWorkerSection.module.scss';

const cx = classNames.bind(style);
const POLL_MS = 10000;

const formatBytes = (n) => {
  if (!n || n <= 0) return '-';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), u.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
};

/**
 * 관리자 노드 페이지 Edge 워커 섹션 (SP-8 / 수용계획서 3.1).
 * remoteManager 가 관리하는 엣지 디바이스(인스턴스 없는 단일 노드) 등록/상태/레이블.
 * 자체완결(own fetch/state/modal) — AdminNodeContent 의 cluster node 흐름과 분리.
 */
const EdgeWorkerSection = () => {
  const { t } = useTranslation();
  const history = useHistory();
  const [workers, setWorkers] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [labelEditFor, setLabelEditFor] = useState(null);
  const [labelKey, setLabelKey] = useState('');
  const [labelValue, setLabelValue] = useState('');
  const fetchingRef = useRef(false);

  const fetchWorkers = useCallback(async () => {
    if (fetchingRef.current) return; // 이전 폴링 진행 중이면 중첩 방지
    fetchingRef.current = true;
    try {
      const res = await getEdgeWorkers();
      if (res.status === STATUS_SUCCESS) setWorkers(res.result || []);
    } finally {
      fetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    fetchWorkers();
    const iv = setInterval(fetchWorkers, POLL_MS); // 저장된 상태 주기 갱신
    return () => clearInterval(iv);
  }, [fetchWorkers]);

  const handleRefresh = useCallback(
    async (id) => {
      setBusyId(id);
      const res = await refreshEdgeWorker(id); // remoteManager 폴링
      setBusyId(null);
      if (res.status === STATUS_SUCCESS) fetchWorkers();
      else toast.error(res.message || t('edge.toast.refreshFail'));
    },
    [fetchWorkers, t],
  );

  const handleDelete = useCallback(
    async (id, deviceId) => {
      // eslint-disable-next-line no-alert
      if (!window.confirm(t('edge.confirm.delete', { device: deviceId })))
        return;
      setBusyId(id);
      const res = await deleteEdgeWorker(id);
      setBusyId(null);
      if (res.status === STATUS_SUCCESS) fetchWorkers();
      else toast.error(res.message || t('edge.toast.deleteFail'));
    },
    [fetchWorkers, t],
  );

  const submitLabel = useCallback(
    async (deviceId) => {
      if (!labelKey.trim()) return;
      const res = await upsertEdgeLabel({
        target_type: 'edge_worker',
        target_id: deviceId,
        label_key: labelKey.trim(),
        label_value: labelValue.trim() || undefined,
      });
      if (res.status === STATUS_SUCCESS) {
        setLabelEditFor(null);
        setLabelKey('');
        setLabelValue('');
        fetchWorkers();
      } else {
        toast.error(res.message || t('edge.toast.labelFail'));
      }
    },
    [labelKey, labelValue, fetchWorkers, t],
  );

  const removeLabel = useCallback(
    async (labelId) => {
      const res = await deleteEdgeLabel(labelId);
      if (res.status === STATUS_SUCCESS) fetchWorkers();
      else toast.error(res.message || t('edge.toast.labelFail'));
    },
    [fetchWorkers, t],
  );

  return (
    <div className={cx('edge-section')}>
      <div className={cx('edge-head')}>
        <div className={cx('edge-title')}>
          {t('edge.section.title')}
          <span className={cx('edge-count')}>{workers.length}</span>
        </div>
        <ButtonV2
          colorType='skyblue'
          size='s'
          label={t('edge.register.title')}
          onClick={() => history.push('/admin/nodes/edge/new')}
        />
      </div>
      <div className={cx('edge-desc')}>{t('edge.section.desc')}</div>

      {workers.length === 0 ? (
        <div className={cx('edge-empty')}>{t('edge.empty')}</div>
      ) : (
        <table className={cx('edge-table')}>
          <thead>
            <tr>
              <th>{t('edge.col.status')}</th>
              <th>{t('edge.col.device')}</th>
              <th>{t('edge.col.type')}</th>
              <th>{t('edge.col.domain')}</th>
              <th>{t('edge.col.deploy')}</th>
              <th>{t('edge.col.resource')}</th>
              <th>{t('edge.col.lastSeen')}</th>
              <th>{t('edge.col.labels')}</th>
              <th>{t('edge.col.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {workers.map((w) => (
              <tr key={w.id}>
                <td>
                  <span className={cx('status', w.conn_status)}>
                    <span className={cx('dot')} />
                    {t(`edge.status.${w.conn_status || 'offline'}`)}
                  </span>
                </td>
                <td>
                  <div className={cx('device-id')}>{w.device_id}</div>
                  {w.name && <div className={cx('device-name')}>{w.name}</div>}
                </td>
                <td>{w.device_type || '-'}</td>
                <td>{w.sdx_domain || '-'}</td>
                <td>
                  {w.deploy_model ? (
                    <span className={cx('deploy', w.deploy_state)}>
                      {w.deploy_model}
                      <span className={cx('deploy-state')}>
                        {' '}
                        {w.deploy_version ? `(${w.deploy_version}) ` : ''}
                        {w.deploy_state || ''}
                      </span>
                    </span>
                  ) : (
                    '-'
                  )}
                </td>
                <td className={cx('resource')}>
                  {w.cpu_cores ? `CPU ${w.cpu_cores} · ` : ''}
                  {w.mem_total ? `${formatBytes(w.mem_total)} · ` : ''}
                  {w.gpu_info || ''}
                  {w.container_count != null
                    ? ` · ${w.container_count} cont.`
                    : ''}
                  {!w.cpu_cores && !w.mem_total && !w.gpu_info ? '-' : ''}
                </td>
                <td className={cx('last-seen')}>{w.last_seen || '-'}</td>
                <td className={cx('labels-cell')}>
                  <div className={cx('chips')}>
                    {(w.labels || []).map((l) => (
                      <span key={l.id} className={cx('chip')}>
                        {l.key}
                        {l.value ? `=${l.value}` : ''}
                        <button
                          type='button'
                          className={cx('chip-x')}
                          onClick={() => removeLabel(l.id)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  {labelEditFor === w.device_id ? (
                    <div className={cx('label-add')}>
                      <input
                        className={cx('label-input')}
                        placeholder={t('edge.label.key')}
                        value={labelKey}
                        onChange={(e) => setLabelKey(e.target.value)}
                        maxLength={64}
                      />
                      <input
                        className={cx('label-input')}
                        placeholder={t('edge.label.value')}
                        value={labelValue}
                        onChange={(e) => setLabelValue(e.target.value)}
                        maxLength={255}
                      />
                      <button
                        type='button'
                        className={cx('label-btn')}
                        onClick={() => submitLabel(w.device_id)}
                      >
                        {t('add.label')}
                      </button>
                      <button
                        type='button'
                        className={cx('label-btn', 'cancel')}
                        onClick={() => {
                          setLabelEditFor(null);
                          setLabelKey('');
                          setLabelValue('');
                        }}
                      >
                        {t('cancel.label')}
                      </button>
                    </div>
                  ) : (
                    <button
                      type='button'
                      className={cx('add-label')}
                      onClick={() => {
                        setLabelEditFor(w.device_id);
                        setLabelKey('');
                        setLabelValue('');
                      }}
                    >
                      + {t('edge.label.add')}
                    </button>
                  )}
                </td>
                <td className={cx('actions')}>
                  <button
                    type='button'
                    className={cx('act')}
                    disabled={busyId === w.id}
                    onClick={() => handleRefresh(w.id)}
                  >
                    {t('edge.action.refresh')}
                  </button>
                  <button
                    type='button'
                    className={cx('act', 'danger')}
                    disabled={busyId === w.id}
                    onClick={() => handleDelete(w.id, w.device_id)}
                  >
                    {t('delete.label')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default EdgeWorkerSection;
