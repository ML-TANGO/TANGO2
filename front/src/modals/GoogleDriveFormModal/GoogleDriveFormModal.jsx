import { useState } from 'react';

// Custom Hooks
import useDataInput from './hooks/useDataInput';

// Components
import GoogleDriveFormModalContent from '@src/components/modalContents/GoogleDriveFormModalContent';
import { toast } from '@src/components/Toast';

// Utils
import {
  defaultSuccessToastMessage,
  errorToastMessage,
  extractPath,
} from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS, STATUS_FAIL } from '@src/network';

function GoogleDriveFormModal({ type, data: modalData }) {
  // Loading
  const [loading, setLoading] = useState(false);

  // Custom Hooks
  // Google Drive(Folder) 입력 폼 커스텀 훅
  const [dataState, renderDataInputForm] = useDataInput();

  // 모든 인풋 유효성 검증 여부 (true 일 경우 저장 버튼 활성화)
  const isValidate = dataState.isValid;

  // 데이터셋 Google Drive api 호출
  const onSubmit = async (callback) => {
    setLoading(true);

    const { accessToken, folderId, folderName, _mimetype } = dataState;
    const { datasetId, loc } = modalData;
    const google_info = {};
    const _access_token = accessToken.split(' ');

    Object.assign(google_info, {
      access_token: _access_token[1],
    });

    Object.assign(google_info, {
      list: [{ id: folderId, name: folderName, mimetype: _mimetype }],
    });

    const form = new FormData();
    form.append('upload_method', 0);
    if (extractPath(loc)) form.append('path', extractPath(loc));
    form.append('dataset_id', datasetId);
    form.append('built_in_method', 1);
    form.append('google_info', JSON.stringify(google_info));

    const response = await callApi({
      url: 'datasets/google_drive',
      method: 'POST',
      body: form,
    });
    const { status, message, error } = response;

    setLoading(false);

    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('upload');
      callback();
      return true;
    }
    if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
      return false;
    }
    toast.error(message);
    return false;
  };

  return (
    <GoogleDriveFormModalContent
      modalData={modalData}
      type={type}
      renderDataInputForm={renderDataInputForm}
      isValidate={isValidate}
      onSubmit={onSubmit}
      loading={loading}
    />
  );
}

export default GoogleDriveFormModal;
