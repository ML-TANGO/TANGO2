import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Components
import DeploymentLogDeleteModalContent from '@src/components/modalContents/DeploymentLogDeleteModalContent';
import { toast } from '@src/components/Toast';

import useDeleteConfirmMessage from '@src/hooks/useDeleteConfirmMessage';

// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

// Custom Hooks
import useTimeSettingInput from './hooks/useTimeSettingInput';

function DeploymentLogDeleteModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const { deploymentId, deploymentName, workerList, notice } = modalData;
  const [workerListByDate, setWorkerListByDate] = useState({
    complete: [],
    partial: [],
  });
  const [workerListMessage, setWorkerListMessage] = useState(null);
  const [timeSettingInputState, renderTimeSettingInput] = useTimeSettingInput();
  const [deleteConfirmMessageState, renderDeleteConfirmMessage] =
    useDeleteConfirmMessage(notice, deploymentName);
  const {
    isRange,
    endDate,
    isValid: timeSettingIsValid,
  } = timeSettingInputState;
  const isValidate = timeSettingIsValid && deleteConfirmMessageState.isValid;

  const getWorkerListByDate = useCallback(
    async (endDate) => {
      const query = `deployment_id=${deploymentId}&end_time=${endDate}`;
      const response = await callApi({
        url: `deployments/worker_list_by_date?${query}`,
        method: 'get',
      });
      const { result, message, status } = response;
      if (status === STATUS_SUCCESS) {
        setWorkerListMessage(null);
        setWorkerListByDate(result);
        return;
      } else if (status === STATUS_FAIL) {
        setWorkerListMessage(message);
      } else {
        setWorkerListMessage('Server Error');
        toast.error('Server Error');
      }
      setWorkerListByDate({
        complete: [],
        partial: [],
      });
    },
    [deploymentId],
  );

  const onSubmit = async (callback) => {
    let query = `deployment_id=${deploymentId}`;
    if (isRange && endDate) {
      query = `${query}&end_time=${endDate}`;
    }
    if (workerList && workerList.length > 0) {
      query = `${query}&worker_list=${workerList.join(', ')}`;
    }
    const response = await callApi({
      url: `deployments/api_log?${query}`,
      method: 'delete',
    });
    const { message, status, error } = response;
    if (status === STATUS_SUCCESS) {
      // toast.success(t('deleteLog.success.toast'));
      callback();
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error('Server Error');
    }
  };

  useEffect(() => {
    if (!workerList && endDate) {
      getWorkerListByDate(endDate);
    }
  }, [endDate, getWorkerListByDate, workerList]);

  return (
    <DeploymentLogDeleteModalContent
      type={type}
      title={t('logDelete.label')}
      modalData={modalData}
      onSubmit={onSubmit}
      isValidate={isValidate && (isRange ? !workerListMessage : true)}
      isConfirmMessage={!isRange || (timeSettingIsValid && !workerListMessage)}
      renderTimeSettingInput={renderTimeSettingInput}
      renderDeleteConfirmMessage={renderDeleteConfirmMessage}
      workerListByDate={isRange && endDate ? workerListByDate : null}
      workerListMessage={workerListMessage}
    />
  );
}

export default DeploymentLogDeleteModal;
