import { loadModalComponent } from '@src/modal';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import UserDeploymentInfoContent from '@src/components/pageContents/user/UserDeploymentInfoContent';

import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function UserDeploymentInfoPage() {
  // Redux Hooks
  const dispatch = useDispatch();

  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const { id: wid, did } = match.params;

  // i18n
  const { t } = useTranslation();

  // State
  const [basicInfo, setBasicInfo] = useState({});
  const [builtInModelInfo, setBuiltInModelInfo] = useState({});
  const [accessInfo, setAccessInfo] = useState({});
  const [usageStatusInfo, setUsageStatusInfo] = useState({});
  const [instanceInfo, setInstanceInfo] = useState({});

  const onDelete = async (did) => {
    const response = await callApi({
      url: `deployments/${did}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      history.push(`/user/workspace/${wid}/deployments`);
    } else {
      errorToastMessage(error, message);
    }
  };

  // Events
  const openEditModal = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_DEPLOYMENT',
        modalData: {
          submit: {
            text: 'edit.label',
          },
          cancel: {
            text: 'cancel.label',
          },
          deploymentId: did,
          workspaceId: wid,
        },
      }),
    );
  };

  /**
   * Action 브래드크럼
   * @param {String} deploymentName
   */
  const breadCrumbHandler = (deploymentName) => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Serving',
            path: `/user/workspace/${wid}/deployments`,
            t,
          },
        },
        {
          component: {
            name: 'Deployment',
            path: `/user/workspace/${wid}/deployments`,
            t,
          },
        },
        {
          component: {
            name: deploymentName,
            path: `/user/workspace/${wid}/deployments/${did}/dashboard`,
          },
        },
        {
          component: {
            name: 'Deployment Info',
            t,
          },
        },
      ]),
    );
  };

  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteDeploymentPopup.title.label',
        content: 'deleteDeploymentPopup.message',
        testid: 'deployment-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete(did);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: basicInfo.name,
      }),
    );
  };

  /**
   * 배포 정보
   */
  const getDeploymentInfo = useCallback(async () => {
    const response = await callApi({
      url: `deployments/detail/${did}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setBasicInfo(result.basic_info);
      setBuiltInModelInfo(result?.built_in_model_info || {});
      setAccessInfo(result.access_info);
      setUsageStatusInfo(result.usage_status_info);
      setInstanceInfo(result.instance_info);
      breadCrumbHandler(result.basic_info.name);
      return true;
    }
    errorToastMessage(error, message);
    return false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [did]);

  /**
   * 로그 다운로드 모달 오픈
   */
  const openDownloadLogModal = () => {
    dispatch(
      openModal({
        modalType: 'DEPLOYMENT_LOG_DOWNLOAD',
        modalData: {
          submit: {
            text: t('download.label'),
            func: () => {
              dispatch(closeModal('DEPLOYMENT_LOG_DOWNLOAD'));
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          deploymentId: did,
          deploymentName: basicInfo.name,
          createDatetime: basicInfo.create_datetime,
        },
      }),
    );
  };

  /**
   * 로그 삭제 모달 오픈
   */
  const openDeleteLogModal = () => {
    dispatch(
      openModal({
        modalType: 'DEPLOYMENT_LOG_DELETE',
        modalData: {
          submit: {
            text: t('delete.label'),
            func: () => {
              dispatch(closeModal('DEPLOYMENT_LOG_DELETE'));
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          deploymentId: did,
          deploymentName: basicInfo.name,
          notice: t('deleteLogPopup.message', { name: basicInfo.name }),
        },
      }),
    );
  };

  /**
   * API 수정 모달 오픈
   */
  const openEditApiModal = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_API',
        modalData: {
          submit: {
            text: t('edit.label'),
            func: () => {
              dispatch(closeModal('EDIT_API'));
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          deploymentId: did,
          apiAddress: usageStatusInfo.api_address,
        },
      }),
    );
  };

  useIntervalCall(getDeploymentInfo, 1000);

  useEffect(() => {
    loadModalComponent('EDIT_DEPLOYMENT');
    loadModalComponent('DEPLOYMENT_LOG_DOWNLOAD');
    loadModalComponent('DEPLOYMENT_LOG_DELETE');
    loadModalComponent('EDIT_API');
  }, []);

  return (
    <UserDeploymentInfoContent
      basicInfo={basicInfo}
      builtInModelInfo={builtInModelInfo}
      accessInfo={accessInfo}
      usageStatusInfo={usageStatusInfo}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      openEditModal={openEditModal}
      openDownloadLogModal={openDownloadLogModal}
      openDeleteLogModal={openDeleteLogModal}
      openEditApiModal={openEditApiModal}
      instanceInfo={instanceInfo}
    />
  );
}

export default UserDeploymentInfoPage;
