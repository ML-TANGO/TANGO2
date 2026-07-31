// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useDeleteConfirmMessage from '@src/hooks/useDeleteConfirmMessage';

// Components
import DeploymentWorkerDeleteModalContent from '@src/components/modalContents/DeploymentWorkerDeleteModalContent/DeploymentWorkerDeleteModalContent';

function DeploymentDeleteModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const message = t('deleteDeployment.message');
  const { notice, deploymentName } = modalData;
  const [deleteConfirmMessageState, renderDeleteConfirmMessage] =
    useDeleteConfirmMessage(notice, deploymentName);

  return (
    <DeploymentWorkerDeleteModalContent // workerDelete랑 같은 거 사용
      type={type}
      title={t('deleteDeploymentPopup.title.label')}
      modalData={modalData}
      renderDeleteConfirmMessage={renderDeleteConfirmMessage}
      isValidate={deleteConfirmMessageState}
      message={message}
    />
  );
}

export default DeploymentDeleteModal;
