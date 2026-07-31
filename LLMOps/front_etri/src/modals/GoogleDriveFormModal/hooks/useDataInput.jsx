import { useState, useMemo } from 'react';

// Components
import DataInputForm from '@src/components/modalContents/GoogleDriveFormModalContent/DataInputForm';

/**
 * 데이터셋 Google Drive 업로드 모달에서 Google Picker폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param {'UPLOAD_GOOGLE_DRIVE'} type
 * @returns {[
 *  {
 *    accessToken: object,
 *    folderId: string,
 *    folderName: string,
 *    dataError: string | undefined,
 *    isValid: boolean,
 *  },
 *  () => JSX.Element
 * ]}
 *
 * @component
 * @example
 *
 * const [
 *  dataState,
 *  renderDataInputForm, // Google Drive 인풋 및 불러오기 버튼 렌더링 함수
 * ] = useDataInput();
 *
 * return (
 *  <>
 *    {renderDataInputForm()}
 *  </>
 * );
 *
 */
const useDataInput = () => {
  // Component State
  const [accessToken, setAccessToken] = useState('');
  const [folderId, setFolderId] = useState('');
  const [folderName, setFolderName] = useState('');
  const [dataError, setDataError] = useState();
  const [_mimetype, setMimetype] = useState('');
  // Events
  const inputHandler = (driveData) => {
    const { accessToken: token, id, name, mimetype } = driveData;
    setAccessToken(token);
    setFolderId(id);
    setFolderName(name);
    setDataError('');
    setMimetype(mimetype);
  };

  // URL 컴포넌트 렌더링 함수
  const renderDataInput = () => {
    return <DataInputForm inputHandler={inputHandler} />;
  };

  const result = useMemo(
    () => ({
      accessToken,
      folderId,
      folderName,
      isValid: dataError === '',
      _mimetype,
    }),
    [accessToken, folderId, folderName, dataError, _mimetype],
  );

  return [result, renderDataInput];
};

export default useDataInput;
