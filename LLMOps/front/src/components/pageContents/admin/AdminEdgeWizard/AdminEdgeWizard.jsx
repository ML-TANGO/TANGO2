import { useMemo, useRef, useState } from 'react';
import { useHistory } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import { toast } from '@src/components/Toast';
import { STATUS_SUCCESS } from '@src/network';
import { copyToClipboardWithToast } from '@src/utils';
import {
  issueEdgeToken,
  registerEdgeWorker,
  upsertEdgeLabel,
} from '@src/apis/flightbase/edge';

import classNames from 'classnames/bind';
import style from './AdminEdgeWizard.module.scss';

const cx = classNames.bind(style);

const NODES_PATH = '/admin/nodes';

// 목업 디바이스 트랙 (device_type 값 유지 — BE/SP-6 정합).
const TRACKS = [
  { value: 'orin', labelKey: 'edge.track.orin' },
  { value: 'rpi-hailo', labelKey: 'edge.track.rpiHailo' },
  { value: 'pc-gpu', labelKey: 'edge.track.pcGpu' },
];

// 소속 기관 (sdx_domain). 기타 = 빈 값.
const ORGS = [
  { value: 'SDS', labelKey: 'edge.org.sds' },
  { value: 'SDF', labelKey: 'edge.org.sdf' },
  { value: 'SDM', labelKey: 'edge.org.sdm' },
  { value: '', labelKey: 'edge.org.etc' },
];

// BE 검증과 동일 패턴(model.py). 잘못된 값이 서버로 가기 전에 클라이언트에서 차단.
const DEVICE_ID_RE = /^[A-Za-z0-9._-]+$/;
const LABEL_KEY_RE = /^[A-Za-z0-9._/-]+$/;

/**
 * Edge 등록 위저드 (풀페이지 2-step, admin). SP-8 확장.
 * Step1 정보 입력 → registerEdgeWorker(+레이블 upsert) → Step2 API 안내 + 토큰 발급.
 */
const AdminEdgeWizard = () => {
  const { t } = useTranslation();
  const history = useHistory();

  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    device_id: '',
    name: '',
    device_type: 'orin',
    hw_model: '',
    sdx_domain: 'SDS',
    location: '',
    remote_manager_url: '',
  });
  const [labels, setLabels] = useState([]); // [{key, value}]
  const [labelKey, setLabelKey] = useState('');
  const [labelValue, setLabelValue] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState(null); // {id, device_id}
  const [issuing, setIssuing] = useState(false);
  const [token, setToken] = useState(null); // {token, token_prefix, expires_at}
  const submittingRef = useRef(false);
  const issuingRef = useRef(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const deviceIdValid = useMemo(
    () => DEVICE_ID_RE.test(form.device_id.trim()),
    [form.device_id],
  );
  const urlValid = useMemo(() => {
    const u = form.remote_manager_url.trim();
    return u === '' || /^https?:\/\/.+/.test(u);
  }, [form.remote_manager_url]);
  const canSubmit = deviceIdValid && urlValid && !submitting;

  const addLabel = () => {
    const key = labelKey.trim();
    if (!key) return;
    if (!LABEL_KEY_RE.test(key)) {
      toast.error(t('edge.label.invalidKey'));
      return;
    }
    if (labels.some((l) => l.key === key)) return;
    setLabels((ls) => [...ls, { key, value: labelValue.trim() }]);
    setLabelKey('');
    setLabelValue('');
  };
  const removeLabel = (key) =>
    setLabels((ls) => ls.filter((l) => l.key !== key));

  const goToNodes = () => {
    if (submitting) return; // 등록 진행 중엔 이탈 금지(백그라운드 토스트/상태 누수 방지).
    history.push(NODES_PATH);
  };

  const handleRegister = async () => {
    if (!canSubmit || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    const body = {
      device_id: form.device_id.trim(),
      name: form.name.trim() || undefined,
      device_type: form.device_type || undefined,
      hw_model: form.hw_model.trim() || undefined,
      sdx_domain: form.sdx_domain || undefined,
      location: form.location.trim() || undefined,
      remote_manager_url: form.remote_manager_url.trim() || undefined,
    };
    const res = await registerEdgeWorker(body);
    if (res.status !== STATUS_SUCCESS) {
      submittingRef.current = false;
      setSubmitting(false);
      toast.error(res.message || t('edge.toast.registerFail'));
      return;
    }
    const worker = res.result || {};
    // 레이블은 등록 성공 후 device_id 기준으로 개별 upsert. 실패는 수집해 경고(등록 자체는 유지).
    let labelFailed = false;
    for (const l of labels) {
      // eslint-disable-next-line no-await-in-loop
      const lr = await upsertEdgeLabel({
        target_type: 'edge_worker',
        target_id: body.device_id,
        label_key: l.key,
        label_value: l.value || undefined,
      });
      if (lr.status !== STATUS_SUCCESS) labelFailed = true;
    }
    submittingRef.current = false;
    setSubmitting(false);
    setCreated({ id: worker.id, device_id: body.device_id });
    if (labelFailed) toast.error(t('edge.toast.labelPartial'));
    else toast.success(t('edge.toast.registered'));
    setStep(2);
  };

  const handleIssueToken = async () => {
    if (!created || issuingRef.current) return;
    issuingRef.current = true;
    setIssuing(true);
    const res = await issueEdgeToken(created.id);
    issuingRef.current = false;
    setIssuing(false);
    if (res.status === STATUS_SUCCESS) {
      setToken(res.result || null);
    } else {
      toast.error(res.message || t('edge.toast.tokenFail'));
    }
  };

  // 표시 전용 안내 문자열. 실제 라우트는 fb_resource edge/route.py 의 /edge/devices/{id}/heartbeat.
  // (P3 API 규격 뷰어에서 공용 상수/자산으로 일원화 예정.)
  const heartbeatPath = created
    ? `POST /api/edge/devices/${created.device_id}/heartbeat`
    : '';

  return (
    <div>
      <PageHeader
        title={t('edge.wizard.title')}
        rightComponent={
          <ButtonV2
            type='outline'
            size='s'
            label={t('cancel.label')}
            onClick={goToNodes}
            disabled={submitting}
          />
        }
      />
      <div className={cx('wizard')}>
        {/* 스텝 바 */}
        <div className={cx('steps')}>
          <div className={cx('step', { active: step === 1, done: step > 1 })}>
            <span className={cx('num')}>1</span>
            {t('edge.wizard.step1')}
          </div>
          <div className={cx('bar')} />
          <div className={cx('step', { active: step === 2 })}>
            <span className={cx('num')}>2</span>
            {t('edge.wizard.step2')}
          </div>
        </div>

        {step === 1 && (
          <form
            className={cx('card')}
            onSubmit={(e) => {
              e.preventDefault();
              handleRegister();
            }}
          >
            <div className={cx('card-title')}>
              {t('edge.wizard.step1.title')}
            </div>
            <div className={cx('card-desc')}>{t('edge.wizard.step1.desc')}</div>

            <label className={cx('field-label')} htmlFor='edge-device-id'>
              {t('edge.field.deviceId')} *
            </label>
            <input
              id='edge-device-id'
              className={cx('field-input', {
                invalid: form.device_id && !deviceIdValid,
              })}
              value={form.device_id}
              onChange={set('device_id')}
              placeholder='orin-sds-port-01'
              maxLength={128}
              aria-invalid={!!form.device_id && !deviceIdValid}
              aria-describedby='edge-device-id-hint'
            />
            {form.device_id && !deviceIdValid && (
              <div id='edge-device-id-hint' className={cx('field-error')}>
                {t('edge.field.deviceId.invalid')}
              </div>
            )}

            <label className={cx('field-label')} htmlFor='edge-name'>
              {t('edge.field.name')}
            </label>
            <input
              id='edge-name'
              className={cx('field-input')}
              value={form.name}
              onChange={set('name')}
              maxLength={128}
            />

            <label className={cx('field-label')} htmlFor='edge-track'>
              {t('edge.field.track')}
            </label>
            <select
              id='edge-track'
              className={cx('field-input')}
              value={form.device_type}
              onChange={set('device_type')}
            >
              {TRACKS.map((d) => (
                <option key={d.value} value={d.value}>
                  {t(d.labelKey)}
                </option>
              ))}
            </select>

            <label className={cx('field-label')} htmlFor='edge-hw-model'>
              {t('edge.field.hwModel')}
            </label>
            <input
              id='edge-hw-model'
              className={cx('field-input')}
              value={form.hw_model}
              onChange={set('hw_model')}
              placeholder='Jetson AGX Orin 64GB · Jetpack 6.0'
              maxLength={128}
            />

            <label className={cx('field-label')} htmlFor='edge-org'>
              {t('edge.field.sdxDomain')}
            </label>
            <select
              id='edge-org'
              className={cx('field-input')}
              value={form.sdx_domain}
              onChange={set('sdx_domain')}
            >
              {ORGS.map((o) => (
                <option key={o.labelKey} value={o.value}>
                  {t(o.labelKey)}
                </option>
              ))}
            </select>

            <label className={cx('field-label')} htmlFor='edge-location'>
              {t('edge.field.location')}
            </label>
            <input
              id='edge-location'
              className={cx('field-input')}
              value={form.location}
              onChange={set('location')}
              maxLength={255}
            />

            <label className={cx('field-label')} htmlFor='edge-rm-url'>
              {t('edge.field.remoteManager')}
            </label>
            <input
              id='edge-rm-url'
              className={cx('field-input', { invalid: !urlValid })}
              value={form.remote_manager_url}
              onChange={set('remote_manager_url')}
              placeholder='http://192.168.0.x:8080'
              maxLength={512}
              aria-invalid={!urlValid}
              aria-describedby='edge-rm-url-hint'
            />
            <div id='edge-rm-url-hint' className={cx('field-hint')}>
              {urlValid
                ? t('edge.wizard.urlHint')
                : t('edge.field.remoteManager.invalid')}
            </div>

            <label className={cx('field-label')}>
              {t('edge.field.labels')}
            </label>
            <div className={cx('chips')}>
              {labels.map((l) => (
                <span key={l.key} className={cx('chip')}>
                  {l.key}
                  {l.value ? `=${l.value}` : ''}
                  <button
                    type='button'
                    className={cx('chip-x')}
                    onClick={() => removeLabel(l.key)}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className={cx('label-add')}>
              <input
                className={cx('label-input')}
                placeholder={t('edge.label.key')}
                value={labelKey}
                onChange={(e) => setLabelKey(e.target.value)}
                maxLength={64}
                aria-label={t('edge.label.key')}
              />
              <input
                className={cx('label-input')}
                placeholder={t('edge.label.value')}
                value={labelValue}
                onChange={(e) => setLabelValue(e.target.value)}
                maxLength={255}
                aria-label={t('edge.label.value')}
              />
              <button
                type='button'
                className={cx('label-btn')}
                onClick={addLabel}
              >
                + {t('add.label')}
              </button>
            </div>

            <div className={cx('actions')}>
              <ButtonV2
                type='outline'
                label={t('cancel.label')}
                onClick={goToNodes}
                disabled={submitting}
              />
              <ButtonV2
                colorType='blue'
                label={t('edge.wizard.next')}
                onClick={handleRegister}
                disabled={!canSubmit}
              />
            </div>
          </form>
        )}

        {step === 2 && (
          <div className={cx('card')}>
            <div className={cx('card-title')}>
              {t('edge.wizard.step2.title')}
            </div>
            <div className={cx('card-desc')}>{t('edge.wizard.step2.desc')}</div>

            <div className={cx('api-box')}>
              <div className={cx('api-line')}>{heartbeatPath}</div>
              <div className={cx('api-line', 'sub')}>
                Authorization: Bearer {'{edge_token}'}
              </div>
              <div className={cx('api-hint')}>
                {t('edge.wizard.heartbeatHint')}
              </div>
            </div>

            {token ? (
              <div className={cx('token-box')}>
                <div className={cx('token-warning')}>
                  {t('edge.token.warning')}
                </div>
                <div className={cx('token-row')}>
                  <code className={cx('token-value')}>{token.token}</code>
                  <button
                    type='button'
                    className={cx('label-btn')}
                    onClick={() => copyToClipboardWithToast(token.token)}
                  >
                    {t('edge.token.copy')}
                  </button>
                </div>
                <div className={cx('token-meta')}>
                  {t('edge.token.prefix')}: {token.token_prefix} ·{' '}
                  {t('edge.token.expires')}: {token.expires_at}
                </div>
              </div>
            ) : (
              <ButtonV2
                colorType='skyblue'
                label={t('edge.token.issue')}
                onClick={handleIssueToken}
                disabled={issuing}
              />
            )}

            <div className={cx('actions')}>
              <ButtonV2
                type='outline'
                label={t('edge.wizard.viewSpec')}
                onClick={() => history.push('/admin/nodes/edge/api-spec')}
              />
              <ButtonV2
                colorType='blue'
                label={t('edge.wizard.done')}
                onClick={() => history.push(NODES_PATH)}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminEdgeWizard;
