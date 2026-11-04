import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Components
import ModalFrame from '@src/components/Modal/ModalFrame';
import SystemLogModal from '@src/components/Modal/SystemLogModal';
import { toast } from '@src/components/Toast';

import useIntervalCall from '@src/hooks/useIntervalCall';
// Custom Hooks
import useWindowDimensions from '@src/hooks/useWindowDimensions';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';

function SystemLogModalContainer({ data: modalData }) {
  const { width } = useWindowDimensions();
  const {
    deploymentWorkerId,
    systemLogData,
    systemLogLoading,
    traingId,
    projectName,
    isHideScreenFromProps,
  } = modalData;

  const { t } = useTranslation();
  const [systemLog, setSystemLog] = useState('');

  const [downLoading, setDownLoading] = useState(false);
  const newSubmit = {
    text: 'confirm.label',
    func: () => {
      modalData.submit.func();
    },
  };
  const systemLogDown = async (id) => {
    if (!traingId && !deploymentWorkerId) return;
    setDownLoading(true);
    const response = await network.callApiWithPromise({
      url: traingId
        ? `projects/training-system-log-download?training_id=${traingId}`
        : `deployments/worker/system_log_download/${deploymentWorkerId}`,
      method: 'GET',
    });

    const { data, status } = response;

    if (status === 200 && data !== 'Not Found Pod') {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = traingId
        ? `[Project]${projectName} - [Job]${id}.log`
        : `[Worker] ${deploymentWorkerId}`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      toast.error(t('downloadError'));
    }
    setDownLoading(false);
  };

  const fetchSystemLog = useCallback(async () => {
    const response = await callApi({
      url: traingId
        ? `projects/training-system-log?training_id=${traingId}`
        : `deployments/worker/system_log/${deploymentWorkerId}`,
      method: 'get',
    });

    const { status, message, error, result } = response;
    if (status === STATUS_SUCCESS) {
      setSystemLog(result);
    }

    return true;
  }, [traingId, deploymentWorkerId]);

  useEffect(() => {
    fetchSystemLog();
  }, []);

  useIntervalCall(fetchSystemLog, 1000);

  return (
    <>
      <ModalFrame
        submit={newSubmit}
        type={'SYSTEM_LOG'}
        validate={true}
        isResize={true}
        isMinimize={true}
        title={
          deploymentWorkerId
            ? `[${t('worker')} ${deploymentWorkerId}] ${t('systemLog.label')}`
            : t('training')
        }
        customStyle={{
          width: width > 1920 ? '1800px' : width > 1200 ? '1200px' : '780px',
        }}
        isHideScreenFromProps={isHideScreenFromProps}
      >
        <SystemLogModal
          workerId={deploymentWorkerId}
          head={t('systemLog.label')}
          data={systemLogData}
          systemLogLoading={systemLogLoading}
          systemLogDown={systemLogDown}
          downLoading={downLoading}
          systemLog={systemLog}
          t={t}
          traingId={traingId}
        />
      </ModalFrame>
    </>
  );
}

export default SystemLogModalContainer;
