import { TRAINING_TOOL_TYPE } from '@src/types';
import { useCallback, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

import DockerImageFormModalContent from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalContent';
import DockerImageFormModalFooter from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalFooter';
import DockerImageFormModalHeader from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalHeader';
import { toast } from '@src/components/Toast';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal, openModal } from '@src/store/modules/modal';

import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage, executeWithLogging } from '@src/utils';

import ToolCardContent from './ToolCardContent';
import ToolCardFooter from './ToolCardFooter/ToolCardFooter';
import ToolCardHeader from './ToolCardHeader';
import ToolCardTable from './ToolCardTable/ToolCardTable';

import classNames from 'classnames/bind';
import style from './ToolCard.module.scss';

const cx = classNames.bind(style);

const calPodContent = ({ podType, idx, ip, gpuName, gpu, cpu, ram }) => {
  const title = idx === '0' ? `${podType}` : `${podType} #${idx}`;
  return [
    { label: title, value: '' },
    { label: 'IP', value: ip ?? '-' },
    { label: 'vGPU', value: gpuName && gpu ? `${gpuName} x ${gpu}EA` : '-' },
    { label: 'vCPU', value: cpu ? `${cpu} cores` : '-' },
    { label: 'vRAM', value: ram ? `${ram} GB` : '-' },
  ];
};

const calRunningMessage = (toolLoading, resourceType, status, gpuCount, t) => {
  if (toolLoading) {
    return t('joblist.exit.message');
  }

  if (status === 'installing') {
    return t('job.installing.message');
  }

  if (['pending', 'scheduling'].includes(status)) {
    if (resourceType === 'gpu') {
      if (gpuCount === 0) {
        return t('job.pending.message');
      }
      return t('job.gpu.pending.message');
    }
    return t('job.cpu.pending.message');
  }

  if (['failed', 'error'].includes(status)) {
    if (resourceType === 'gpu') {
      return t('job.gpu.fail.message');
    }
    if (resourceType === 'cpu') {
      return t('job.cpu.fail.message');
    }
    return t('job.error.message');
  }
  return ' ';
};

const calToogleButtonColor = (status, toolLoading) => {
  const yellowStatus = ['pending', 'scheduling'];

  if (yellowStatus.includes(status) || toolLoading.current) {
    return { backgroundColor: '#ffab31' };
  }

  if (status === 'installing') {
    return { backgroundColor: '#00C775' };
  }

  if (status === 'failed' || status === 'error') {
    return { backgroundColor: '#eb3e2a' };
  }

  return {};
};

// ** [tool Switch 변경 Api] **
const putToolApi = async (id, checked, toolLoading) => {
  toolLoading.current = true;

  const {
    status: apiStatus,
    message,
    error,
  } = await callApi({
    url: 'projects/control_training_tool',
    method: 'put',
    body: {
      project_tool_id: id,
      action: checked ? 'off' : 'on',
    },
  });

  if (apiStatus === STATUS_SUCCESS) {
    console.log('switch success');
  } else if (apiStatus === STATUS_FAIL) {
    errorToastMessage(error, message);
  } else {
    toast.error(message);
  }

  toolLoading.current = false;
};

const activeStatusList = [
  'running',
  'pending',
  'failed',
  'installing',
  'error',
  'scheduling',
];

const sshInfoInitial = {
  sshUrl: '',
  toolPassword: '',
  sshGuideInfo: {
    user: '',
    ingressIp: '',
    toolIp: '',
  },
};

function ToolCard({
  id,
  data,
  toolResource,
  tool_type: toolTypeId,
  tool_type_name: typeName,
  status: toolStatus,
  functionInfoArr,
  on_off_possible: isSwitchPossible,
  tool_commit_status,
  isHideExplanation,
  isPermission = false,
}) {
  const { t, i18n } = useTranslation();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { id: wid, tid } = match.params;

  const {
    id: projectToolId,
    tool_index,
    status,
    image_name,
    gpu_cluster_ips,
    gpu_count,
  } = data;

  const { cpu, ram, resourceName } = toolResource;
  const gpuName = resourceName?.replace('NVIDIA', '');
  const resourceType = gpuName ? 'gpu' : 'cpu';

  const toolType = TRAINING_TOOL_TYPE[toolTypeId]?.type || 'default';
  const toolLabel = TRAINING_TOOL_TYPE[toolTypeId]?.label;
  const toolName = toolLabel || typeName || '';

  // ! 카드 헤더 관련
  // ** 카드 헤더 함수  **
  const handleDeleteTool = useCallback(async (project_tool_id) => {
    executeWithLogging(async () => {
      const { status, message, error } = await callApi({
        url: 'projects/tool-delete',
        method: 'post',
        body: {
          project_tool_id: project_tool_id,
        },
      });

      if (status === STATUS_SUCCESS) {
        return;
      } else {
        errorToastMessage(error, message);
      }
    });
  }, []);

  // ! 스위치 관련
  const toolLoading = useRef(false);
  const switchBackgroundColor = calToogleButtonColor(
    toolStatus.status,
    toolLoading,
  );
  const checked = activeStatusList.includes(toolStatus.status);

  // ** Switch 확인 팝업
  const handletoolConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'toolTermination.label',
        content: 'toolTerminationPopup.message',
        submit: {
          text: 'accept.label',
          func: () => {
            putToolApi(id, checked, toolLoading);
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

  // ** GPU 할당 모달
  const handleGpuAllocateModal = () => {
    dispatch(
      openModal({
        modalType: 'TOOL_GPU_ALLOCATE',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              putToolApi(id, checked, toolLoading);
              dispatch(closeModal('TOOL_GPU_ALLOCATE'));
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          toolId: id,
          toolType: toolTypeId,
          toolName,
          projectId: tid,
          t,
        },
      }),
    );
  };

  const handleSwitch = (toolStatus) => {
    if (
      ['running', 'pending', 'installing', 'error', 'scheduling'].includes(
        toolStatus?.status,
      )
    ) {
      handletoolConfirmPopup();
    } else {
      handleGpuAllocateModal();
    }
  };

  // ! 메세지 관련
  const runningMessage = calRunningMessage(
    toolLoading.current,
    resourceType,
    toolStatus?.status,
    gpu_count,
    t,
  );
  const { backgroundColor } = calToogleButtonColor(
    toolStatus?.status,
    toolLoading,
  );
  const runningMessageColor = backgroundColor ?? '#2D76F8';

  // ! 테이블 관련
  const masterPodValue = gpu_cluster_ips.find((info) => info.index === '0');
  const masterPodArr = useMemo(() => {
    if (gpu_cluster_ips.length === 0) {
      return calPodContent({
        podType: 'Master Pod',
        idx: '0',
        ip: null,
        gpuName,
        gpu: gpu_count,
        cpu,
        ram,
      });
    }
    return calPodContent({
      podType: 'Master Pod',
      idx: '0',
      ip: masterPodValue.ip,
      gpuName,
      gpu: masterPodValue.gpu_count,
      cpu,
      ram,
    });
  }, [gpu_cluster_ips, masterPodValue, gpu_count, gpuName, cpu, ram]);

  const workerPodArr = useMemo(() => {
    const workerPodList = gpu_cluster_ips.filter((info) => info.index !== '0');
    const changeWorkerList = workerPodList.reduce((acc, cur, idx) => {
      const rowValue = calPodContent({
        podType: 'Worker Pod',
        idx: idx + 1,
        ip: cur.ip,
        gpuName,
        gpu: cur.gpu_count,
        cpu,
        ram,
      });
      acc.push(rowValue);
      return acc;
    }, []);
    return changeWorkerList;
  }, [cpu, gpu_cluster_ips, ram, gpuName]);

  const flatWorkerPodList = workerPodArr.flatMap((x) => x);
  const containerArr = [{ label: 'Container Image', value: image_name ?? '-' }];
  const executreList = [...containerArr, ...masterPodArr, ...flatWorkerPodList];

  // ! Footer 관련
  const btnDisable = toolStatus.status !== 'running';
  const menuBtnList = useMemo(() => {
    return [
      {
        name: t('delete.label'),
        iconPath: '/images/icon/00-ic-basic-delete.svg',
        onClick: () => handleDeleteTool(projectToolId),
        disable: !['done', 'stop'].includes(status.status),
      },
    ];
  }, [projectToolId, status, t, handleDeleteTool]);

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
          toolId: id,
        },
      }),
    );
  };

  // ** SSH 정보 가져오는 함수
  const [sshInfo, setSshInfo] = useState(sshInfoInitial);
  const { sshGuideInfo } = sshInfo;

  const fetchSshInfo = useCallback(async () => {
    const { result, status } = await callApi({
      url: 'projects/tool-ssh',
      method: 'get',
      params: {
        project_id: tid,
        project_tool_id: projectToolId,
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
  }, [tid, projectToolId]);

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
          sshGuideInfo,
          sshInfo,
        },
      }),
    );
  };

  const isSshModal = useRef(false);
  const handleSshBtn = () => {
    isSshModal.current = !isSshModal.current;
    fetchSshInfo();
  };

  //  ** Tool 새창에서 열기
  const isToolLinkLoading = useRef(false);
  const handleExcuteLink = async () => {
    isToolLinkLoading.current = true;
    const response = await callApi({
      url: `projects/tool-url?project_tool_id=${id}&protocol=${window.location.protocol.replace(
        ':',
        '',
      )}`,
      method: 'get',
    });

    const { result, status: apiStatus, message, error } = response;
    if (apiStatus === STATUS_SUCCESS) {
      if (result.url !== '') {
        window.open(result.url, '_blank');
      } else {
        if (result?.need_password_change) {
          onPasswordChange(false);
        }
      }
    } else if (apiStatus === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
    isToolLinkLoading.current = false;
  };

  /**
   * 도구 비밀번호 변경 모달
   * 현재는 파일브라우저만 해당
   * @param {boolean} isReset 재설정 유무
   */
  const onPasswordChange = (isReset) => {
    dispatch(
      openModal({
        modalType: 'TOOL_PASSWORD_CHANGE',
        modalData: {
          submit: {
            text: isReset ? 'update.label' : 'create.label',
            func: () => {
              dispatch(closeModal('TOOL_PASSWORD_CHANGE'));
              if (!isReset) {
                handleExcuteLink();
              }
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          toolId: id,
          toolType: toolTypeId,
          toolName,
          isReset,
        },
      }),
    );
  };

  const handleCheckFilebrowserFirst = async () => {
    const response = await callApi({
      url: `trainings/filebrowser-first-entry?training_tool_id=${id}&protocol=${window.location.protocol.replace(
        ':',
        '',
      )}`,
      method: 'get',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result) {
        onPasswordChange(false);
      } else {
        onPasswordChange(true);
      }
    } else {
      errorToastMessage(error, message);
    }
  };

  return (
    <div className={cx('tool-card')}>
      <ToolCardHeader
        toolName={toolName}
        toolType={toolType}
        toolReplicaNum={0}
        menuBtnList={menuBtnList}
      />
      <ToolCardContent
        // ** 툴 이름 관련 **
        toolName={toolName}
        toolTypeId={toolTypeId}
        tool_index={tool_index}
        toolStatus={toolStatus}
        // ** 스위치 관련 **
        isDisabledSwitch={tool_commit_status}
        isSwitchPossible={isSwitchPossible}
        switchBackgroundColor={switchBackgroundColor}
        checked={checked}
        handleSwitch={() => handleSwitch(toolStatus)}
        // ** 메세지 관련 **
        runningMessageColor={runningMessageColor}
        runningMessage={runningMessage}
        isHideExplanation={isHideExplanation}
        i18n={i18n}
      />
      <ToolCardTable executreList={executreList} t={t} />
      <ToolCardFooter
        t={t}
        status={status}
        toolType={toolType}
        btnDisable={btnDisable}
        sshInfo={sshInfo}
        isSshModal={isSshModal}
        isToolLinkLoading={isToolLinkLoading}
        toolLoading={toolLoading}
        isPermission={isPermission}
        functionInfoArr={functionInfoArr}
        handleCommitBtn={handleCommitBtn}
        handleSshGuideBtn={handleSshGuideBtn}
        handleSshBtn={handleSshBtn}
        handleCheckFilebrowserFirst={handleCheckFilebrowserFirst}
        handleExcuteLink={handleExcuteLink}
      />
    </div>
  );
}

export default ToolCard;
