// i18n
import { useTranslation } from 'react-i18next';

// Components
import EditApiModalContent from '@src/components/modalContents/EditApiModalContent/EditApiModalContent';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';

// Custom Hooks
import useApiInput from './hooks/useApiInput';

function EditApiModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const { deploymentId, apiAddress } = modalData;
  const [apiInputState, setApiInputState, renderApiInput] =
    useApiInput(apiAddress);
  const isValidate = apiInputState.isValid;

  const onSubmit = async (callback) => {
    const { endpoint } = apiInputState;
    const body = {
      deployment_id: deploymentId,
      api_path: endpoint,
    };
    const response = await callApi({
      url: 'deployments/api_path',
      method: 'put',
      body,
    });
    const { message, status } = response;
    if (status === STATUS_SUCCESS) {
      // toast.success(message);
      callback();
    } else if (status === STATUS_FAIL) {
      setApiInputState({ endpointError: message });
    } else {
      toast.error('Fail');
    }
  };

  return (
    <EditApiModalContent
      title={t('editApiAddress.title.label')}
      onSubmit={onSubmit}
      isValidate={isValidate}
      type={type}
      modalData={modalData}
      renderApiInput={renderApiInput}
    />
  );
}

export default EditApiModal;
