import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import DeployWorkerMemoModal from '@src/components/Modal/DeployWorkerMemoModal';

function DeployWorkerMemoModalContainer({ data, type }) {
  const [memo, setMemo] = useState(data.prevMemo ? data.prevMemo : '');
  const { t } = useTranslation();

  const textareaInputHandler = (e) => {
    const { value } = e.target;
    setMemo(value);
  };

  return (
    <DeployWorkerMemoModal
      data={data}
      type={type}
      memo={memo}
      textareaInputHandler={textareaInputHandler}
      workerId={data.workerId}
      t={t}
    />
  );
}

export default DeployWorkerMemoModalContainer;
