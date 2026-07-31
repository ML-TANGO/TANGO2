import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Loading, Radio } from '@jonathan/ui-react';

import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import EmptyBox from '@src/components/molecules/EmptyBox';

import { getPlayground } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './ExpertInferenceModal.module.scss';

const cx = classNames.bind(style);

// 배포 상태는 조나단 Badge type으로 매핑한다.
const DEPLOYMENT_BADGE_TYPE = {
  running: 'green',
};

// 전문가 평가 시작 전 "추론에 사용할 배포" 선택 모달.
//   워크스페이스의 running 배포(playground)를 나열 → 선택 시 그 배포 모델로 지연 단위 VLM
//   실추론(전문가가 여는 샘플만). 선택 안 함 → mock 출력으로 진행(graceful). running 없으면 mock 안내.
//   (배포↔프로젝트 모델 매칭은 사용자 선택 신뢰 — 리스트 API 가 비-dual 모델 id 를 안 실어줌.)
const ExpertInferenceModal = ({ workspaceId, onConfirm, onClose }) => {
  const { t } = useTranslation();

  const [deployments, setDeployments] = useState(null); // null=로딩, []=없음
  const [selected, setSelected] = useState(null); // playground id | null(mock)

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
      const running = raw.filter((p) => p && p.status === 'running');
      setDeployments(running);
      // 실추론이 happy path — running 이 하나면 기본 선택, 여럿/없음이면 사용자 선택.
      if (running.length === 1) setSelected(running[0].id);
    })();
    return () => {
      active = false;
    };
  }, [workspaceId]);

  // NewStyleModalFrame은 Redux 모달 스택(modalKeys.at(-1))을 닫는데, 이 모달은 Redux 가 아닌
  // 로컬 showInferModal 로 렌더된다. 그래서 (a) Esc 를 capture 단계에서 가로채
  // stopImmediatePropagation 으로 프레임의 document 핸들러 발화를 막고(안 막으면 무관한 다른
  // Redux 모달이 같이 닫힌다), (b) 이 모달만 닫는다.
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key !== 'Escape') return;
      event.stopImmediatePropagation();
      onClose();
    };
    document.addEventListener('keydown', handleEscape, true);
    return () => document.removeEventListener('keydown', handleEscape, true);
  }, [onClose]);

  // 프레임이 마운트 시 body.overflow='hidden' 만 걸고 unmount 복구가 없다
  // (NewStyleModalFrame.jsx 의 effect 에 cleanup 없음). Redux 모달은 스토어 변경 경로로
  // 복구되지만 로컬 조건부 렌더는 그 경로를 안 타므로, 평가 시작·백드롭 닫기 후 페이지
  // 스크롤이 잠긴 채 남는다 → 언마운트 시 직접 복구한다.
  useEffect(
    () => () => {
      document.body.style.overflow = 'auto';
    },
    [],
  );

  const loading = deployments === null;
  const submit = {
    text: 'evaluation.expert.inferStart',
    func: () => onConfirm(selected),
  };
  const cancel = {
    text: 'cancel.label',
    func: onClose,
  };
  const modalTitle = t('evaluation.expert.inferTitle');

  return (
    <div
      onClick={(event) => {
        // 기존 수제 오버레이와 동일하게 프레임 바깥을 누르면 닫는다.
        if (event.target.id === modalTitle) onClose();
      }}
    >
      <NewStyleModalFrame
        type='expertInferenceModal'
        title={modalTitle}
        submit={submit}
        cancel={cancel}
        validate={!loading}
        isResize
        isMinimize
        customStyle={{ width: '664px' }}
      >
        <div className={cx('inference-content')}>
          <p className={cx('desc')}>{t('evaluation.expert.inferDesc')}</p>

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
                      name='expertInferenceDeployment'
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
              <div className={cx('deployment-row')}>
                <div className={cx('deployment-choice')}>
                  <Radio
                    name='expertInferenceDeployment'
                    options={[
                      {
                        label: t('evaluation.expert.inferNone'),
                        value: 'mock',
                      },
                    ]}
                    selectedValue={selected === null ? 'mock' : selected}
                    onChange={() => setSelected(null)}
                  />
                </div>
              </div>
              {deployments.length === 0 && (
                <EmptyBox
                  text='evaluation.expert.inferNoRunning'
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

export default ExpertInferenceModal;
