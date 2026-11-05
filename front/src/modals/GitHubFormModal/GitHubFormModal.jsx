import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useUrlInput from './hooks/useUrlInput';
import useAccessInput from './hooks/useAccessInput';

// Components
import GitHubFormModalContent from '@src/components/modalContents/GitHubFormModalContent';
import { toast } from '@src/components/Toast';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS, STATUS_FAIL } from '@src/network';

function GitHubFormModal({ type, data: modalData }) {
  const { t } = useTranslation();

  // Loading
  const [loading, setLoading] = useState(false);

  // Custom Hooks
  // URL + 폴더이름 입력 폼 커스텀 훅
  const [urlState, renderUrlInputForm] = useUrlInput(modalData);

  // Access 입력 폼 커스텀 훅
  const [accessState, renderAccessInputForm] = useAccessInput();

  // 모든 인풋 유효성 검증 여부 (true 일 경우 저장 버튼 활성화)
  const isValidate = urlState.isValid;

  // 데이터셋 GitHub Clone api 호출
  const onSubmit = async (callback) => {
    setLoading(true);

    const { url, folderName } = urlState;
    const { username, accessToken } = accessState;
    const { datasetId, loc } = modalData;

    const body = {
      url,
      dir: folderName,
      dataset_id: datasetId,
      current_path: loc,
    };

    if (username !== '' && accessToken !== '') {
      body.username = username;
      body.accesstoken = accessToken;
    }

    const response = await callApi({
      url: 'datasets/github_clone',
      method: 'POST',
      body,
    });
    const { result, status, message, error } = response;

    setLoading(false);

    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('clone');
      callback();
      return true;
    }
    if (status === STATUS_FAIL) {
      if (result.is_private) {
        toast.error(t('githubPrivate.message'));
      } else {
        errorToastMessage(error, message);
      }
      return false;
    }
    toast.error(message);
    return false;
  };

  return (
    <GitHubFormModalContent
      modalData={modalData}
      type={type}
      renderUrlInputForm={renderUrlInputForm}
      renderAccessInputForm={renderAccessInputForm}
      isValidate={isValidate}
      onSubmit={onSubmit}
      loading={loading}
    />
  );
}

export default GitHubFormModal;
