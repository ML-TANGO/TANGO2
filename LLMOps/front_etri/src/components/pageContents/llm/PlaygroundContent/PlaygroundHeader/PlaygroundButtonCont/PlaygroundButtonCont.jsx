import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@tango/ui-react';

import { openModal } from '@src/store/modules/modal';

import useDeployBtn from './hooks/useDelpoyBtn';
import useSaveBtn from './hooks/useSaveBtn';
import useStopbtn from './hooks/useStopBtn';

export default function PlaygroundButtonCont({ isFetchingStatus }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { params } = match;
  const playgroundId = params.did;

  const { isStopBtn, isStopLoading, handleStop } = useStopbtn();
  const { isSaveBtn, handleSave } = useSaveBtn(isFetchingStatus, playgroundId);
  const {
    init_deployment,
    isDeployLoading,
    isDeployBtn,
    isCompleteRunning,
    handleDeploy,
  } = useDeployBtn();

  // ** [액션] 테스트 버튼 핸들러 **
  const handleTest = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'PLAYGROUND_TEST_MODAL',
        modalData: {
          playgroundId,
        },
      }),
    );
  }, [dispatch, playgroundId]);

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
        label={t('Test')}
        onClick={handleTest}
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
