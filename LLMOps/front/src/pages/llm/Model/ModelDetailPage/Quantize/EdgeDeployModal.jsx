import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { toast } from '@src/components/Toast';
import { STATUS_SUCCESS } from '@src/network';
import { deployEdgeWorker, getEdgeWorkers } from '@src/apis/flightbase/edge';
import { getQuantizeDevices } from '@src/apis/llm/model';

import classNames from 'classnames/bind';
import style from './QuantizeModal/QuantizeModal.module.scss';

const cx = classNames.bind(style);

/**
 * 양자화 포팅 패키지(GGUF)를 Edge 워커에 배포 (SP-6 / 3.10).
 * Edge 워커 선택 + device→권장Q 호환성 힌트 + 기관 이미지 입력 → remoteManager /ops.
 * onClose(refreshed: bool).
 */
const EdgeDeployModal = ({ open, onClose, modelName, jobId, ggufFile, targetQuant }) => {
  const { t } = useTranslation();
  const [workers, setWorkers] = useState([]);
  const [devices, setDevices] = useState([]);
  const [workerId, setWorkerId] = useState('');
  const [image, setImage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    (async () => {
      const [wr, dr] = await Promise.all([getEdgeWorkers(), getQuantizeDevices()]);
      if (!alive) return;
      if (wr.status === STATUS_SUCCESS) setWorkers(wr.result || []);
      else toast.error(t('edgeDeploy.toast.loadFail')); // 빈 목록과 fetch 실패 구분
      if (dr.status === STATUS_SUCCESS) setDevices(dr.result?.devices || []);
      setWorkerId('');
      setImage('');
    })();
    return () => {
      alive = false;
    };
  }, [open]);

  const selectedWorker = workers.find((w) => String(w.id) === String(workerId));
  const recommended = useMemo(() => {
    if (!selectedWorker) return null;
    return devices.find((x) => x.key === selectedWorker.device_type)?.recommended || null;
  }, [selectedWorker, devices]);

  if (!open) return null;

  const compatMatch = recommended && recommended === targetQuant;

  const handleDeploy = async () => {
    if (!workerId || !image.trim() || !ggufFile || !jobId) return;
    setSubmitting(true);
    const res = await deployEdgeWorker(workerId, {
      image: image.trim(),
      model_name: modelName || undefined,
      model_version: targetQuant || undefined,
      gguf_path: ggufFile && jobId ? `jobs/${jobId}/output/${ggufFile}` : undefined,
    });
    setSubmitting(false);
    if (res.status === STATUS_SUCCESS) {
      toast.success(t('edgeDeploy.toast.ok'));
      onClose(true);
    } else {
      toast.error(res.message || t('edgeDeploy.toast.fail'));
    }
  };

  return (
    <div className={cx('overlay')} onClick={submitting ? undefined : () => onClose(false)}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('title')}>{t('edgeDeploy.title')}</div>
        <div className={cx('subtitle')}>
          {t('edgeDeploy.desc', {
            model: modelName || '',
            quant: String(targetQuant || '').toUpperCase(),
          })}
        </div>

        <div className={cx('section-label')}>{t('edgeDeploy.worker')}</div>
        <select
          className={cx('device-select')}
          value={workerId}
          onChange={(e) => setWorkerId(e.target.value)}
          disabled={submitting}
        >
          <option value=''>{t('edgeDeploy.worker.select')}</option>
          {workers.map((w) => (
            <option key={w.id} value={w.id} disabled={w.conn_status !== 'online'}>
              {w.device_id} ({w.device_type || '?'}) — {w.conn_status}
            </option>
          ))}
        </select>
        {workers.length === 0 && (
          <div className={cx('reco-reason')}>{t('edgeDeploy.noWorker')}</div>
        )}

        {selectedWorker && recommended && (
          <div className={cx('reco-badge')}>
            {t('edgeDeploy.reco', { quant: recommended.toUpperCase() })}
            <span className={cx('reco-reason')}>
              {compatMatch
                ? t('edgeDeploy.compat.ok')
                : t('edgeDeploy.compat.warn', { pkg: String(targetQuant || '').toUpperCase() })}
            </span>
          </div>
        )}

        <div className={cx('section-label')}>{t('edgeDeploy.image')}</div>
        <input
          className={cx('device-input')}
          value={image}
          onChange={(e) => setImage(e.target.value)}
          placeholder='docker.io/org/edge-runtime:tag'
          maxLength={512}
          disabled={submitting}
        />
        <div className={cx('reco-reason')}>{t('edgeDeploy.image.hint')}</div>

        <div className={cx('section-label')}>{t('edgeDeploy.package')}</div>
        <div className={cx('reco-reason')}>
          jobs/{jobId}/output/{ggufFile || '-'}
        </div>

        <div className={cx('actions')}>
          <ButtonV2
            type='outline'
            label={t('cancel.label')}
            onClick={() => onClose(false)}
            disabled={submitting}
          />
          <ButtonV2
            colorType='blue'
            label={t('edgeDeploy.submit')}
            onClick={handleDeploy}
            disabled={submitting || !workerId || !image.trim() || !ggufFile || !jobId}
          />
        </div>
      </div>
    </div>
  );
};

export default EdgeDeployModal;
