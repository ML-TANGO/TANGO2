import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

import useDeployBtn from './hooks/useDelpoyBtn';
import useSaveBtn from './hooks/useSaveBtn';
import useStopbtn from './hooks/useStopBtn';

export default function PlaygroundButtonCont({ isFetchingStatus }) {
  const { t } = useTranslation();
  const history = useHistory();

  const match = useRouteMatch();
  const { params } = match;
  const playgroundId = params.did;
  const workspaceId = params.id;

  const { isStopBtn, isStopLoading, handleStop } = useStopbtn();
  const { isSaveBtn, handleSave } = useSaveBtn(isFetchingStatus, playgroundId);
  const {
    init_deployment,
    isDeployLoading,
    isDeployBtn,
    isCompleteRunning,
    handleDeploy,
  } = useDeployBtn();

  // ** [액션] 추론 탭으로 이동 (D6: 추론은 별도 탭. running 배포만 질의 가능) **
  const handleGoInference = useCallback(() => {
    history.push(`/user/workspace/${workspaceId}/inference/${playgroundId}`);
  }, [history, workspaceId, playgroundId]);

  return (
    <>
      <ButtonV2
        colorType='skyblue'
        label={t('saveBtn.label')}
        onClick={handleSave}
        disabled={!isSaveBtn}
      />
      <ButtonV2
        colorType='skyblue'
        label={t('inference.goTo')}
        onClick={handleGoInference}
        disabled={!isCompleteRunning || isFetchingStatus}
      />
      <ButtonV2
        colorType='blue'
        label={!init_deployment ? t('Deployment') : t('reserving')}
        disabled={!isDeployBtn || isFetchingStatus}
        onClick={() => {
          if (isDeployLoading) return;
          handleDeploy();
        }}
        isLoading={isDeployLoading}
      />
      <ButtonV2
        colorType='red'
        label={t('stop')}
        onClick={() => handleStop(t)}
        disabled={!isStopBtn || isFetchingStatus}
        isLoading={isStopLoading}
      />
    </>
  );
}
