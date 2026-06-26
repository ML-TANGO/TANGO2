import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { getQuantizeDevices } from '@src/apis/llm/model';
import { STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './QuantizeModal.module.scss';

const cx = classNames.bind(style);

// SP-4 코어: Q4/Q5/Q6 (llama.cpp GGUF). 비트수↓ = 용량↓·정확도↓·디바이스 친화↑.
const QUANT_OPTIONS = [
  { value: 'q4', titleKey: 'quantize.q4.label', descKey: 'quantize.q4.desc' },
  { value: 'q5', titleKey: 'quantize.q5.label', descKey: 'quantize.q5.desc' },
  { value: 'q6', titleKey: 'quantize.q6.label', descKey: 'quantize.q6.desc' },
];

const CUSTOM = '__custom__';

/**
 * 양자화 옵션 모달 (자체 오버레이 — Redux modal registry 비의존).
 * Q4/Q5/Q6 + 타겟 디바이스(권장 Q 배지·자동제안, 4.5) + 프루닝 토글(4.7 placeholder).
 */
const QuantizeModal = ({ open, onClose, onConfirm, submitting }) => {
  const { t } = useTranslation();
  const [quant, setQuant] = useState('q5');
  const [deviceKey, setDeviceKey] = useState(''); // '' = 미선택, CUSTOM = 직접입력
  const [customDevice, setCustomDevice] = useState('');
  const [prune, setPrune] = useState(false);
  const [devices, setDevices] = useState([]); // [{key,label,recommended,reason}]

  // 4.5 device→권장Q 매핑 로드 (BE authoritative)
  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      const res = await getQuantizeDevices();
      if (alive && res.status === STATUS_SUCCESS) setDevices(res.result?.devices ?? []);
    })();
    return () => {
      alive = false;
    };
  }, [open]);

  if (!open) return null;

  const selected = devices.find((d) => d.key === deviceKey);

  const handleDeviceChange = (e) => {
    const key = e.target.value;
    setDeviceKey(key);
    const dev = devices.find((d) => d.key === key);
    if (dev?.recommended) setQuant(dev.recommended); // 권장 Q 자동제안 (override 가능)
  };

  const handleConfirm = () => {
    let target_device;
    if (deviceKey === CUSTOM) target_device = customDevice.trim() || undefined;
    else if (deviceKey) target_device = deviceKey;
    onConfirm({ target_quant: quant, target_device, prune });
  };

  return (
    <div className={cx('overlay')} onClick={submitting ? undefined : onClose}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('title')}>{t('quantize.modal.title')}</div>
        <div className={cx('subtitle')}>{t('quantize.modal.desc')}</div>

        <div className={cx('section-label')}>{t('quantize.device.label')}</div>
        <select
          className={cx('device-select')}
          value={deviceKey}
          onChange={handleDeviceChange}
          disabled={submitting}
        >
          <option value=''>{t('quantize.device.none')}</option>
          {devices.map((d) => (
            <option key={d.key} value={d.key}>
              {d.label}
            </option>
          ))}
          <option value={CUSTOM}>{t('quantize.device.custom')}</option>
        </select>
        {deviceKey === CUSTOM && (
          <input
            className={cx('device-input')}
            type='text'
            placeholder={t('quantize.device.placeholder')}
            value={customDevice}
            onChange={(e) => setCustomDevice(e.target.value)}
            disabled={submitting}
            maxLength={64}
          />
        )}
        {selected && (
          <div className={cx('reco-badge')}>
            {t('quantize.reco.badge', {
              quant: String(selected.recommended || '').toUpperCase(),
            })}
            <span className={cx('reco-reason')}>{selected.reason}</span>
          </div>
        )}

        <div className={cx('section-label')}>{t('quantize.level.label')}</div>
        <div className={cx('options')}>
          {QUANT_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={cx('option', quant === opt.value && 'selected')}
            >
              <input
                type='radio'
                name='target_quant'
                value={opt.value}
                checked={quant === opt.value}
                onChange={() => setQuant(opt.value)}
                disabled={submitting}
              />
              <div className={cx('option-text')}>
                <div className={cx('option-title')}>
                  {t(opt.titleKey)}
                  {selected?.recommended === opt.value && (
                    <span className={cx('reco-tag')}>{t('quantize.reco.tag')}</span>
                  )}
                </div>
                <div className={cx('option-desc')}>{t(opt.descKey)}</div>
              </div>
            </label>
          ))}
        </div>

        <label className={cx('prune-row')}>
          <input
            type='checkbox'
            checked={prune}
            onChange={(e) => setPrune(e.target.checked)}
            disabled={submitting}
          />
          <div className={cx('prune-text')}>
            <span className={cx('prune-title')}>{t('quantize.prune.label')}</span>
            <span className={cx('prune-desc')}>{t('quantize.prune.desc')}</span>
          </div>
        </label>

        <div className={cx('actions')}>
          <ButtonV2
            type='outline'
            label={t('cancel.label')}
            onClick={onClose}
            disabled={submitting}
          />
          <ButtonV2
            colorType='blue'
            label={t('quantize.start.label')}
            onClick={handleConfirm}
            disabled={submitting}
          />
        </div>
      </div>
    </div>
  );
};

export default QuantizeModal;
