// i18n
import { useTranslation } from 'react-i18next';

// Components
import DeployWorkerStopModal from '@src/components/Modal/DeployWorkerStopModal';

function DeployWorkerStopModalContainer({ data, type }) {
  const { t } = useTranslation();

  return <DeployWorkerStopModal data={data} t={t} type={type} />;
}

export default DeployWorkerStopModalContainer;
