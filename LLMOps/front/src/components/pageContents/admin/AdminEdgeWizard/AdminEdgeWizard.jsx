import { useMemo, useRef, useState } from 'react';
import { useHistory } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import { toast } from '@src/components/Toast';
import { STATUS_SUCCESS } from '@src/network';
import { copyToClipboardWithToast } from '@src/utils';
import { issueEdgeToken, registerEdgeWorker } from '@src/apis/flightbase/edge';

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

/**
 * Edge 등록 위저드 (풀페이지 2-step, admin). SP-8 확장.
 * Step1 정보 입력 → registerEdgeWorker → Step2 API 안내 + 토큰 발급.
 * device_id 는 서버가 자동 생성(edge-<hex>) → Step2 에서 확인. 이름은 필수·중복 불가(BE 체크).
 */
const AdminEdgeWizard = () => {
  const { t } = useTranslation();
  const history = useHistory();

  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    name: '',
    device_type: 'orin',
    remote_manager_url: '',
  });

  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState(null); // {id, device_id}
  const [issuing, setIssuing] = useState(false);
  const [token, setToken] = useState(null); // {token, token_prefix, expires_at}
  const submittingRef = useRef(false);
  const issuingRef = useRef(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const nameValid = useMemo(() => form.name.trim().length > 0, [form.name]);
  const urlValid = useMemo(() => {
    const u = form.remote_manager_url.trim();
    return u === '' || /^https?:\/\/.+/.test(u);
  }, [form.remote_manager_url]);
  const canSubmit = nameValid && urlValid && !submitting;

  const goToNodes = () => {
    if (submitting) return; // 등록 진행 중엔 이탈 금지(백그라운드 토스트/상태 누수 방지).
    history.push(NODES_PATH);
  };

  const handleRegister = async () => {
    if (!canSubmit || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    const body = {
      name: form.name.trim(),
      device_type: form.device_type || undefined,
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
    submittingRef.current = false;
    setSubmitting(false);
    // device_id 는 서버가 생성해 응답으로 내려줌 → Step2 에서 표시.
    setCreated({ id: worker.id, device_id: worker.device_id });
    toast.success(t('edge.toast.registered'));
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

            <label className={cx('field-label')} htmlFor='edge-name'>
              {t('edge.field.name')} *
            </label>
            <input
              id='edge-name'
              className={cx('field-input')}
              value={form.name}
              onChange={set('name')}
              placeholder='orin-sds-port-01'
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

            {/* 서버가 자동 생성한 device_id — 물리 장비 설정/heartbeat 에 이 값을 사용. */}
            {created && (
              <div className={cx('api-box')}>
                <div className={cx('api-hint')}>{t('edge.field.deviceId')}</div>
                <div className={cx('token-row')}>
                  <code className={cx('token-value')}>
                    {created.device_id}
                  </code>
                  <button
                    type='button'
                    className={cx('label-btn')}
                    onClick={() => copyToClipboardWithToast(created.device_id)}
                  >
                    {t('edge.token.copy')}
                  </button>
                </div>
              </div>
            )}

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
