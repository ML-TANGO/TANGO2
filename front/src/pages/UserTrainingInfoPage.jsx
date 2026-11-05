import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import UserTrainingInfoContent from '@src/components/pageContents/user/UserTrainingInfoContent/UserTrainingInfoContent';

import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { openModal } from '@src/store/modules/modal';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function UserTrainingInfoPage() {
  const { t } = useTranslation();

  // Redux Hooks
  const dispatch = useDispatch();

  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const { id: wid, tid } = match.params;

  // State
  const [basicInfo, setBasicInfo] = useState({});
  const [builtInModelInfo, setBuiltInModelInfo] = useState({});
  const [accessInfo, setAccessInfo] = useState({});
  const [instanceInfo, setInstanceInfo] = useState({});

  const onDelete = async (tid) => {
    const response = await callApi({
      url: `projects`,
      method: 'delete',
      body: {
        id_list: [tid],
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      history.push(`/user/workspace/${wid}/trainings`);
    } else {
      errorToastMessage(error, message);
    }
  };

  // Events
  const openEditModal = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_TRAINING',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              // refreshData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          trainingId: tid,
          workspaceId: wid,
        },
      }),
    );
  };

  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteTrainingPopup.title.label',
        content: 'deleteTrainingPopup.message',
        testid: 'training-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete(tid);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: basicInfo.name,
      }),
    );
  };

  const allStop = async () => {
    const response = await callApi({
      url: `trainings/stop?training_id=${tid}`,
      method: 'get',
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('stop');
    } else {
      errorToastMessage(error, message);
    }
  };

  const getTrainingInfo = useCallback(async () => {
    const response = await callApi({
      url: `projects/detail/${tid}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const newBasicInfo = {
        name: result.name,
        description: result.description,
        createDatetime: result.create_datetime,
        createName: result?.create_user_name,
      };

      const newAccessInfo = {
        userList: result.users,
        owner: result.manager_name,
        access: result.access,
      };

      const newInstanceInfo = {
        instanceCount: result.instance_allocate,
        instanceName: result.instance_name,
        gpu: result.gpu_allocate,
        gpuName: result.resource_name,
        cpu: result.instance_cpu,
        ram: result.instance_ram,
        type: result?.type,
        huggingfaceId: result?.huggingface_model_id,
        category: result?.category,
        builtInModel: result?.built_in_model,
      };
      setBasicInfo(newBasicInfo);
      setInstanceInfo(newInstanceInfo);
      // setBuiltInModelInfo(result?.built_in_model_info || {});
      setAccessInfo(newAccessInfo);
      breadCrumbHandler(result.name);
      return true;
    }
    errorToastMessage(error, message);
    return false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tid]);

  useIntervalCall(getTrainingInfo, 1000);

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
            path: `/user/workspace/${wid}/trainings/${tid}/workbench`,
          },
        },
        {
          component: { name: 'Training Info', t },
        },
      ]),
    );
  };

  useEffect(() => {
    loadModalComponent('EDIT_TRAINING');
  }, []);

  return (
    <UserTrainingInfoContent
      basicInfo={basicInfo}
      // builtInModelInfo={builtInModelInfo}
      accessInfo={accessInfo}
      instanceInfo={instanceInfo}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      openEditModal={openEditModal}
      allStop={allStop}
    />
  );
}

export default UserTrainingInfoPage;
