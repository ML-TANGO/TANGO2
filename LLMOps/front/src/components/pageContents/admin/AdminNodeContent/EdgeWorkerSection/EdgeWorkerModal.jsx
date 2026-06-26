import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './EdgeWorkerSection.module.scss';

const cx = classNames.bind(style);

// SP-6/Runtime edge 정합 디바이스 타입.
const DEVICE_TYPES = [
  { value: '', labelKey: 'edge.deviceType.unset' },
  { value: 'orin', label: 'Jetson Orin' },
  { value: 'rpi-hailo', label: 'Raspberry Pi + Hailo' },
  { value: 'pc-gpu', label: 'PC (GPU)' },
  { value: 'server', label: 'Server' },
];

/**
 * Edge 워커 등록 모달 (자체 오버레이). open/onClose/onSubmit/submitting props.
 * device_id + remote_manager_url 필수. 나머지 선택.
 */
const EdgeWorkerModal = ({ open, onClose, onSubmit, submitting }) => {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    device_id: '',
    name: '',
    device_type: '',
    sdx_domain: '',
    remote_manager_url: '',
  });

  // 모달은 open=false 일 때도 마운트 유지(if(!open) return null) → 재오픈 시 폼 초기화
  // (이전 입력한 device_id 잔류 방지).
  useEffect(() => {
    if (open) {
      setForm({ device_id: '', name: '', device_type: '', sdx_domain: '', remote_manager_url: '' });
    }
  }, [open]);

  if (!open) return null;

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const canSubmit = form.device_id.trim() && form.remote_manager_url.trim();

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit({
      device_id: form.device_id.trim(),
      name: form.name.trim() || undefined,
      device_type: form.device_type || undefined,
      sdx_domain: form.sdx_domain.trim() || undefined,
      remote_manager_url: form.remote_manager_url.trim(),
    });
  };

  return (
    <div className={cx('overlay')} onClick={submitting ? undefined : onClose}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('modal-title')}>{t('edge.register.title')}</div>
        <div className={cx('modal-desc')}>{t('edge.register.desc')}</div>

        <label className={cx('field-label')}>{t('edge.field.deviceId')} *</label>
        <input
          className={cx('field-input')}
          value={form.device_id}
          onChange={set('device_id')}
          placeholder='orin-01'
          maxLength={128}
          disabled={submitting}
        />

        <label className={cx('field-label')}>{t('edge.field.name')}</label>
        <input
          className={cx('field-input')}
          value={form.name}
          onChange={set('name')}
          maxLength={128}
          disabled={submitting}
        />

        <label className={cx('field-label')}>{t('edge.field.deviceType')}</label>
        <select
          className={cx('field-input')}
          value={form.device_type}
          onChange={set('device_type')}
          disabled={submitting}
        >
          {DEVICE_TYPES.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label || t(d.labelKey)}
            </option>
          ))}
        </select>

        <label className={cx('field-label')}>{t('edge.field.sdxDomain')}</label>
        <input
          className={cx('field-input')}
          value={form.sdx_domain}
          onChange={set('sdx_domain')}
          placeholder='smartfarm'
          maxLength={64}
          disabled={submitting}
        />

        <label className={cx('field-label')}>{t('edge.field.remoteManager')} *</label>
        <input
          className={cx('field-input')}
          value={form.remote_manager_url}
          onChange={set('remote_manager_url')}
          placeholder='http://192.168.0.x:8080'
          maxLength={512}
          disabled={submitting}
        />
        <div className={cx('field-hint')}>{t('edge.field.remoteManager.hint')}</div>

        <div className={cx('modal-actions')}>
          <ButtonV2
            type='outline'
            label={t('cancel.label')}
            onClick={onClose}
            disabled={submitting}
          />
          <ButtonV2
            colorType='blue'
            label={t('edge.register.submit')}
            onClick={handleSubmit}
            disabled={submitting || !canSubmit}
          />
        </div>
      </div>
    </div>
  );
};

export default EdgeWorkerModal;
