import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import DockerImageFormModalContent from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalContent';
import DockerImageFormModalFooter from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalFooter';
import DockerImageFormModalHeader from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalHeader';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal, openModal } from '@src/store/modules/modal';

import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
import { copyToClipboard, errorToastMessage } from '@src/utils';

const useDevTool = ({ type, did, id: toolID, wid }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [sshInfo, setSshInfo] = useState({
    sshUrl: '',
    toolPassword: '',
    sshGuideInfo: {
      user: '',
      ingressIp: '',
      toolIp: '',
    },
  });

  // pending, scheduling -> orange
  // installing -> green
  // failed, error -> red
  // default(running) -> blue
  const getBackgroundColor = (status) => {
    if (status === 'pending' || status === 'scheduling') {
      return { backgroundColor: '#FFAB31' };
    }
    if (status === 'installing') {
      return { backgroundColor: '#00C775' };
    }
    if (status === 'failed' || status === 'error') {
      return { backgroundColor: '#FA4E57' };
    }

    return {};
  };

  const getMessage = (status) => {
    if (status === 'pending' || status === 'scheduling')
      return t('job.gpu.pending.message');
    if (status === 'failed' || status === 'error')
      return t('job.gpu.fail.message');
    if (status === 'installing') return '개발 환경을 구성 중 입니다.';

    return '';
  };

  const handleSshGuideBtn = () => {
    dispatch(
      openModal({
        modalType: 'SSH_CONNECTION_GUIDE',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('SSH_CONNECTION_GUIDE'));
            },
          },
          sshGuideInfo: sshInfo.sshGuideInfo,
          sshInfo,
        },
      }),
    );
  };

  const handleCopySshInfo = (value, message) => {
    if (!value) return;
    copyToClipboard(value);
    toast.success(message);
  };

  const handleOpenResourceModal = () => {
    dispatch(
      openModal({
        modalType: 'DATASET_RESOURCE',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {},
          },
          cancel: {
            text: 'cancel.label',
          },
          tool: type,
          preprocessing_id: did,
          preprocessing_tool_id: toolID,
        },
      }),
    );
  };

  const handleCommitBtn = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_DOCKER_IMAGE',
        modalData: {
          headerRender: DockerImageFormModalHeader,
          contentRender: DockerImageFormModalContent,
          footerRender: DockerImageFormModalFooter,
          submit: {
            text: 'create.label',
            func: () => {
              dispatch(closeModal('CREATE_DOCKER_IMAGE'));
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          dockerImage: '',
          isCommit: true,
          workspaceId: wid,
          toolId: toolID,
        },
      }),
    );
  };

  const fetchSshInfo = useCallback(async () => {
    const { result, status } = await callApi({
      url: 'preprocessing/tool/ssh',
      method: 'get',
      params: {
        preprocessing_tool_id: toolID,
      },
    });

    if (status === STATUS_SUCCESS) {
      const { ssh_url, tool_password, ingress_ip, tool_ip, user } = result;
      setSshInfo({
        sshUrl: ssh_url,
        toolPassword: tool_password,
        sshGuideInfo: {
          user,
          ingressIp: ingress_ip,
          toolIp: tool_ip,
        },
      });
    }
  }, [toolID]);

  const handleExcuteLink = async () => {
    const response = await callApi({
      url: `preprocessing/tool/url?preprocessing_tool_id=${toolID}`,
      method: 'get',
    });

    const { result, status: apiStatus, message, error } = response;
    if (apiStatus === STATUS_SUCCESS) {
      if (result.url !== '') {
        window.open(result.url, '_blank');
      } else {
        if (result?.need_password_change) {
          // onPasswordChange(false);
        }
      }
    } else if (apiStatus === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
  };

  // 422 error가 나온다.
  const offTool = async () => {
    const { status, message, error } = await callApi({
      url: 'preprocessing/tool/run',
      method: 'put',
      body: {
        preprocessing_tool_id: toolID,
        action: 'off',
      },
    });
  };

  const deleteTool = async () => {
    const { status, message, error } = await callApi({
      url: 'preprocessing/tool',
      method: 'delete',
      body: {
        preprocessing_tool_id: toolID,
      },
    });
  };

  const deleteToolConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: '도구 삭제',
        content: 'toolTerminationPopup.message',
        submit: {
          text: 'accept.label',
          func: () => {
            deleteTool();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteDeploymentPopup.content.message'),
        contentCustomStyle: {
          color: 'rgba(116, 116, 116, 1)',
        },
      }),
    );
  };

  const handletoolConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'toolTermination.label',
        content: 'toolTerminationPopup.message',
        submit: {
          text: 'accept.label',
          func: () => {
            offTool();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteDeploymentPopup.content.message'),
        contentCustomStyle: {
          color: 'rgba(116, 116, 116, 1)',
        },
      }),
    );
  };

  return {
    getBackgroundColor,
    getMessage,
    handleSshGuideBtn,
    handleCopySshInfo,
    handleOpenResourceModal,
    handleCommitBtn,
    fetchSshInfo,
    handleExcuteLink,
    handletoolConfirmPopup,
    deleteToolConfirmPopup,
    sshInfo,
  };
};

export default useDevTool;
