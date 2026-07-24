import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { getPlayground } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from '../ExpertEvaluation/ExpertInferenceModal.module.scss';

const cx = classNames.bind(style);

// 평가 추론 러너(generate) 실행 모달 — 대상 running 배포를 골라 데이터셋 전량 batch 추론으로
// output 을 생성·영속(_samples). system_prompt 는 이 생성 런이 소유하는 시스템 프롬프트로,
// 헤더 고정 박스(생성 시스템 프롬프트)에 표시되고 채점(benchmark/judge/expert)이 그 output 을
// 소비한다(생성·채점 분리). 재사용 경로(running 배포 선택)만 — 전용 인스턴스 할당은 후속(P4).
const EvalGenerateModal = ({ workspaceId, running, onConfirm, onClose }) => {
  const { t } = useTranslation();

  const [deployments, setDeployments] = useState(null); // null=로딩, []=없음
  const [selected, setSelected] = useState(null); // playground id
  const [sysPrompt, setSysPrompt] = useState('');

  useEffect(() => {
    let active = true;
    (async () => {
      const res = await getPlayground(workspaceId);
      if (!active) return;
      if (res.status !== STATUS_SUCCESS) {
        errorToastMessage(res.error, res.message);
        setDeployments([]);
        return;
      }
      const raw = Array.isArray(res.result) ? res.result : [];
      const runningDeploys = raw.filter((p) => p && p.status === 'running');
      setDeployments(runningDeploys);
      // running 이 하나면 기본 선택, 여럿/없음이면 사용자 선택.
      if (runningDeploys.length === 1) setSelected(runningDeploys[0].id);
    })();
    return () => {
      active = false;
    };
  }, [workspaceId]);

  const loading = deployments === null;

  return (
    <div className={cx('overlay')} onClick={onClose}>
      <div
        className={cx('modal')}
        onClick={(e) => e.stopPropagation()}
        role='dialog'
        aria-modal='true'
      >
        <div className={cx('modal-head')}>
          <h2 className={cx('modal-title')}>
            {t('evaluation.generate.title')}
          </h2>
          <button type='button' className={cx('close-btn')} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={cx('modal-body')}>
          <p className={cx('desc')}>{t('evaluation.generate.desc')}</p>

          <div>
            <label className={cx('sys-label')} htmlFor='eval-gen-sysprompt'>
              {t('evaluation.generate.systemPrompt')}
            </label>
            <textarea
              id='eval-gen-sysprompt'
              className={cx('sys-prompt')}
              rows={4}
              maxLength={4000}
              placeholder={t('evaluation.generate.systemPromptPlaceholder')}
              value={sysPrompt}
              onChange={(e) => setSysPrompt(e.target.value)}
            />
          </div>

          {loading ? (
            <p className={cx('empty')}>{t('evaluation.project.loading')}</p>
          ) : (
            <div className={cx('deploy-list')}>
              {deployments.map((d) => (
                <button
                  key={d.id}
                  type='button'
                  className={cx('deploy-card', selected === d.id && 'on')}
                  onClick={() => setSelected(d.id)}
                >
                  <span className={cx('radio', selected === d.id && 'on')} />
                  <span className={cx('deploy-name')}>{d.name}</span>
                  <span className={cx('deploy-badge')}>running</span>
                </button>
              ))}
              {deployments.length === 0 && (
                <p className={cx('hint')}>
                  {t('evaluation.generate.noRunning')}
                </p>
              )}
            </div>
          )}
        </div>

        <div className={cx('modal-foot')}>
          <button type='button' className={cx('cancel-btn')} onClick={onClose}>
            {t('cancel.label')}
          </button>
          <button
            type='button'
            className={cx('confirm-btn')}
            disabled={loading || running || !selected}
            onClick={() =>
              onConfirm({
                inference_playground_id: selected,
                system_prompt: sysPrompt.trim() || undefined,
              })
            }
          >
            {running ? t('evaluation.running') : t('evaluation.generate.start')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EvalGenerateModal;
