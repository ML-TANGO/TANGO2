import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import { getQuantizeCommits, getQuantizeDevices } from '@src/apis/llm/model';
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
 * SDS(외부 학습) 모델은 커밋을 고른다 — 커밋의 LoRA 를 base 에 merge 해 양자화하기 때문(기본 best→최신).
 */
const QuantizeModal = ({ modelId, open, onClose, onConfirm, submitting }) => {
  const { t } = useTranslation();
  const [quant, setQuant] = useState('q5');
  const [deviceKey, setDeviceKey] = useState(''); // '' = 미선택, CUSTOM = 직접입력
  const [customDevice, setCustomDevice] = useState('');
  const [devices, setDevices] = useState([]); // [{key,label,recommended,reason}]
  // SDS 커밋 선택지 — external=false(내부 모델)면 선택 칸을 그리지 않는다.
  const [commitInfo, setCommitInfo] = useState({ external: false, commits: [] });
  const [commitId, setCommitId] = useState(null);
  // 커밋 목록 조회 전에는 시작을 막는다 — 재진입 시 이전 선택이 제출되거나 선택 없이 시작되지 않게.
  const [commitsLoaded, setCommitsLoaded] = useState(false);

  // 4.5 device→권장Q 매핑 로드 (BE authoritative)
  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      const res = await getQuantizeDevices();
      if (alive && res.status === STATUS_SUCCESS)
        setDevices(res.result?.devices ?? []);
    })();
    return () => {
      alive = false;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !modelId) return;
    let alive = true;
    setCommitInfo({ external: false, commits: [] });
    setCommitId(null);
    setCommitsLoaded(false);
    (async () => {
      const res = await getQuantizeCommits(modelId);
      if (!alive) return;
      // 조회 실패면 선택 칸 없이 진행 — BE 가 기본 커밋(best→최신)을 고른다.
      if (res.status === STATUS_SUCCESS) {
        setCommitInfo({
          external: !!res.result?.external,
          commits: res.result?.commits ?? [],
        });
        setCommitId(res.result?.default_commit_id ?? null);
      }
      setCommitsLoaded(true);
    })();
    return () => {
      alive = false;
    };
  }, [open, modelId]);

  if (!open) return null;

  const needsCommit = commitInfo.external;
  const noCommit = needsCommit && !commitId;

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
    onConfirm({
      target_quant: quant,
      target_device,
      ...(needsCommit && commitId ? { commit_id: commitId } : {}),
    });
  };

  return (
    <div className={cx('overlay')} onClick={submitting ? undefined : onClose}>
      <div className={cx('modal')} onClick={(e) => e.stopPropagation()}>
        <div className={cx('title')}>{t('quantize.modal.title')}</div>
        <div className={cx('subtitle')}>{t('quantize.modal.desc')}</div>

        {needsCommit && (
          <>
            <div className={cx('section-label')}>
              {t('quantize.commit.label')}
            </div>
            {noCommit ? (
              <div className={cx('reco-reason')}>{t('quantize.commit.none')}</div>
            ) : (
              <select
                className={cx('device-select')}
                value={commitId ?? ''}
                onChange={(e) => setCommitId(Number(e.target.value))}
                disabled={submitting}
              >
                {commitInfo.commits.map((c) => (
                  <option
                    key={c.commit_id}
                    value={c.commit_id}
                    disabled={!c.quantizable}
                  >
                    {c.commit_name}
                    {c.is_best ? ` (${t('quantize.commit.best')})` : ''}
                    {c.quantizable && !c.has_lora
                      ? ` (${t('quantize.commit.projectorOnly')})`
                      : ''}
                    {!c.quantizable && c.reason ? ` — ${c.reason}` : ''}
                  </option>
                ))}
              </select>
            )}
            <div className={cx('reco-reason')}>{t('quantize.commit.hint')}</div>
          </>
        )}

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
            onChange={(e) =>
              // BFF 패턴 `^[A-Za-z0-9_\- ]{1,64}$` 정합 — 허용 외 문자 즉시 제거(422 방지, #8)
              setCustomDevice(e.target.value.replace(/[^A-Za-z0-9_\- ]/g, ''))
            }
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
                    <span className={cx('reco-tag')}>
                      {t('quantize.reco.tag')}
                    </span>
                  )}
                </div>
                <div className={cx('option-desc')}>{t(opt.descKey)}</div>
              </div>
            </label>
          ))}
        </div>

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
            disabled={submitting || noCommit || !commitsLoaded}
          />
        </div>
      </div>
    </div>
  );
};

export default QuantizeModal;
