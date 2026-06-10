// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useDeleteConfirmMessage from '@src/hooks/useDeleteConfirmMessage';

// Components
import DeploymentWorkerDeleteModalContent from '@src/components/modalContents/DeploymentWorkerDeleteModalContent/DeploymentWorkerDeleteModalContent';

function DeploymentWorkerDeleteModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const message = t('deleteWorker.title.message');
  const { notice, deploymentName } = modalData;
  const [deleteConfirmMessageState, renderDeleteConfirmMessage] =
    useDeleteConfirmMessage(notice, deploymentName);

  return (
    <DeploymentWorkerDeleteModalContent
      type={type}
      title={t('deleteWorkerPopup.title.label')}
      modalData={modalData}
      renderDeleteConfirmMessage={renderDeleteConfirmMessage}
      isValidate={deleteConfirmMessageState}
      message={message}
    />
  );
}

export default DeploymentWorkerDeleteModal;
