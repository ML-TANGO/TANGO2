import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

// Components
import UserFederatedLearningContent from '@src/components/pageContents/user/UserFederatedLearningContent';
import { toast } from '@src/components/Toast';

// Store
import { startPath } from '@src/store/modules/breadCrumb';
// Actions
import { openConfirm } from '@src/store/modules/confirm';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function UserFederatedLearningPage() {
  // Router Hooks
  const match = useRouteMatch();
  const { id: wid, tid } = match.params;

  const { t } = useTranslation();

  // Redux Hooks
  const dispatch = useDispatch();

  // State
  const [trainingName, setTrainingName] = useState('');
  const [isPermission, setIsPermission] = useState(false);
  const [step, setStep] = useState(1);
  const [infoLoading, setInfoLoading] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [joinLoading, setJoinLoading] = useState(false);
  const [clientName, setClientName] = useState('');
  const [rounds, setRounds] = useState([]);

  /**
   * Training Info 받기 위한 함수
   */
  const getTrainingInfo = useCallback(async () => {
    const response = await callApi({
      url: `trainings/detail/${tid}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setTrainingName(result.basic_info.name);
      breadCrumbHandler(result.basic_info.name);
      setIsPermission(result.access_info.permission_level < 4);
    } else {
      errorToastMessage(error, message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tid]);

  /**
   * 컨테이너 조회
   */
  const getContainerInfo = useCallback(async () => {
    setInfoLoading(true);
    const response = await callApi({
      url: `trainings/${tid}/fl-container`,
      method: 'get',
    });
    setInfoLoading(false);
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const {
        active,
        client_name: clientName,
        is_joined: isJoined,
        is_join_request: isJoinRequest,
        rounds,
      } = result;
      // step 1: 컨테이너 생성 전, 2: 합류 요청 전, 3: 합류 요청 후 대기 중, 4: 합류
      if (active === 0) {
        setStep(1);
      } else if (isJoined) {
        setStep(4);
      } else if (isJoinRequest) {
        setStep(3);
      } else {
        setStep(2);
      }
      setClientName(clientName);
      setRounds(rounds);
      return true;
    } else {
      errorToastMessage(error, message);
    }
    return false;
  }, [tid]);

  /**
   * 컨테이너 생성
   */
  const onCreateContainer = async () => {
    setCreateLoading(true);
    const response = await callApi({
      url: `trainings/${tid}/fl-container`,
      method: 'post',
    });
    setCreateLoading(false);
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('create');
      getContainerInfo();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 합류 요청
   */
  const onJoinRequest = async () => {
    setJoinLoading(true);
    const response = await callApi({
      url: `trainings/${tid}/fl-container/join`,
      method: 'post',
    });
    setJoinLoading(false);
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      // toast.success('합류를 요청하였습니다.');
      getContainerInfo();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 컨테이너 삭제 확인 팝업
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteContainerPopup.title.label',
        content: 'deleteContainerPopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDeleteContainer();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
      }),
    );
  };

  /**
   * 컨테이너 삭제
   */
  const onDeleteContainer = async () => {
    setDeleteLoading(true);
    const response = await callApi({
      url: `trainings/${tid}/fl-container`,
      method: 'delete',
    });
    setDeleteLoading(false);
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      getContainerInfo();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Action 브래드크럼
   * @param {String} trainingName
   */
  const breadCrumbHandler = (trainingName) => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Training',
            path: `/user/workspace/${wid}/trainings`,
            t,
          },
        },
        {
          component: {
            name: trainingName,
          },
        },
        {
          component: { name: 'Federated Learning', t },
        },
      ]),
    );
  };

  useEffect(() => {
    getTrainingInfo();
  }, [getTrainingInfo]);

  useIntervalCall(getContainerInfo, 3000);

  return (
    <UserFederatedLearningContent
      trainingName={trainingName}
      isPermission={isPermission}
      step={step}
      clientName={clientName}
      rounds={rounds}
      loading={[infoLoading, createLoading, joinLoading, deleteLoading]}
      onCreateContainer={onCreateContainer}
      onDeleteContainer={openDeleteConfirmPopup}
      onJoinRequest={onJoinRequest}
      getContainerInfo={getContainerInfo}
    />
  );
}

export default UserFederatedLearningPage;
