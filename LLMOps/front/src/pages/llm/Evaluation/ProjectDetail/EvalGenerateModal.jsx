import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading, Radio, Textarea } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import EmptyBox from '@src/components/molecules/EmptyBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { getPlayground } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvalGenerateModal.module.scss';

const cx = classNames.bind(style);

// 배포 상태는 조나단 Badge type으로 매핑한다.
const DEPLOYMENT_BADGE_TYPE = {
  running: 'green',
};

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

  // NewStyleModalFrame은 Redux 모달을 닫으므로, 로컬 조건부 렌더 경로의 Esc 닫기도 유지한다.
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const loading = deployments === null;
  const submit = {
    text: running ? 'evaluation.running' : 'evaluation.generate.start',
    func: () =>
      onConfirm({
        inference_playground_id: selected,
        system_prompt: sysPrompt.trim() || undefined,
      }),
  };
  const cancel = {
    text: 'cancel.label',
    func: onClose,
  };
  const modalTitle = t('evaluation.generate.title');

  return (
    <div
      onClick={(event) => {
        // 기존 수제 오버레이와 동일하게 프레임 바깥을 누르면 닫는다.
        if (event.target.id === modalTitle) onClose();
      }}
    >
      <NewStyleModalFrame
        type='evalGenerateModal'
        title={modalTitle}
        submit={submit}
        cancel={cancel}
        validate={!loading && !running && Boolean(selected)}
        isResize
        isMinimize
        customStyle={{ width: '664px' }}
      >
        <div className={cx('generate-content')}>
          <p className={cx('desc')}>{t('evaluation.generate.desc')}</p>

          <InputBoxWithLabel
            labelText={t('evaluation.generate.systemPrompt')}
            labelSize='medium'
            disableErrorMsg
          >
            <Textarea
              size='large'
              name='eval-gen-sysprompt'
              maxLength={4000}
              options={{ id: 'eval-gen-sysprompt', rows: 4 }}
              placeholder={t('evaluation.generate.systemPromptPlaceholder')}
              value={sysPrompt}
              customStyle={{ width: '100%', minHeight: '112px' }}
              onChange={(event) => setSysPrompt(event.target.value)}
            />
          </InputBoxWithLabel>

          {loading ? (
            <div className={cx('modal-loading')}>
              <Loading />
              <span>{t('evaluation.project.loading')}</span>
            </div>
          ) : (
            <div className={cx('deployment-list')}>
              {deployments.map((deployment) => (
                <div key={deployment.id} className={cx('deployment-row')}>
                  <div className={cx('deployment-choice')}>
                    <Radio
                      name='evalGenerateDeployment'
                      options={[
                        {
                          label: deployment.name,
                          value: deployment.id,
                        },
                      ]}
                      selectedValue={selected}
                      onChange={() => setSelected(deployment.id)}
                    />
                  </div>
                  <Badge
                    label='running'
                    type={DEPLOYMENT_BADGE_TYPE.running}
                    size='sm'
                  />
                </div>
              ))}
              {deployments.length === 0 && (
                <EmptyBox
                  text='evaluation.generate.noRunning'
                  isBox
                  customStyle={{ height: '96px' }}
                />
              )}
            </div>
          )}
        </div>
      </NewStyleModalFrame>
    </div>
  );
};

export default EvalGenerateModal;
