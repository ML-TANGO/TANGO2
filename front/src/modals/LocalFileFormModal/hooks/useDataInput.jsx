import { useState, useMemo } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import DataInputForm from '@src/components/modalContents/LocalFileFormModalContent/DataInputForm';
import { toast } from '@src/components/Toast';

/**
 * 데이터셋 로컬 파일/폴더 업로드 모달에서 파일/폴더 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param
 * @returns {[
 *  {
 *    files: Array,
 *    folders: Array,
 *    filesError: string | undefined,
 *    uploadType: number,
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
 *  renderDataInputForm, // 파일/폴더 인풋 버튼 렌더링 함수
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
  const { t } = useTranslation();

  // Component State
  const [files, setFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [filesError, setFilesError] = useState();
  const [uploadType, setUploadType] = useState(0);
  const uploadTypeOptions = [
    { label: 'file.label', value: 0 },
    { label: 'folder.label', value: 1 },
  ];

  // 유효성 검증
  const checkValidate = (name, value) => {
    if (name === 'files') {
      if (value.length === 0) {
        return 'file.empty.message';
      }
      const fileNameErrorList = [];
      const fileReg = /(?=.*[:?*<>#$%&()"|\\\s])/;
      for (let i = 0; i < value.length; i += 1) {
        const { name: fileName } = value[i];
        if (fileName.match(fileReg)) {
          fileNameErrorList.push(fileName);
        }
      }
      if (fileNameErrorList.length > 0) {
        toast.info(
          t('fileNameChange.message', {
            fileNameList: `${fileNameErrorList.join('\n')}`,
          }),
        );
      }
    }
    return null;
  };

  // 인풋 파일 이벤트 핸들러
  const fileInputHandler = (newFiles) => {
    const prevFiles = files;
    const fileList = [...prevFiles, ...newFiles];
    setFiles(fileList);
    const validate = checkValidate('files', fileList);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }
  };

  // 인풋 파일(폴더) 이벤트 핸들러
  const folderInputHandler = (newFiles) => {
    const prevFiles = files;
    const fileList = [...prevFiles, ...newFiles];
    const folderNameList = [];
    for (let i = 0; i < fileList.length; i += 1) {
      const { webkitRelativePath } = fileList[i];
      const folderName = webkitRelativePath.split('/')[0];
      // eslint-disable-next-line no-continue
      if (folderNameList.indexOf(folderName) > -1) continue;

      folderNameList.push(folderName);
    }
    setFiles(fileList);
    setFolders(folderNameList);

    const validate = checkValidate('files', fileList);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }
  };

  // 라디오 버튼 이벤트 핸들러
  const radioBtnHandler = (e) => {
    const { value } = e.target;
    // 이 모달에서 name은 항상 uploadType
    setUploadType(parseInt(value, 10)); // 파일(0) or 폴더(1)
    setFiles([]);
    setFolders([]);
    setFilesError(null);
  };

  // 인풋 파일 삭제 이벤트 핸들러
  const onRemoveFiles = (idx) => {
    const newFiles = [
      ...files.slice(0, idx),
      ...files.slice(idx + 1, files.length),
    ];
    setFiles(newFiles);

    const validate = checkValidate('files', newFiles);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }
  };

  // 인풋 폴더 삭제 이벤트 핸들러
  const onRemoveFolder = (name, idx) => {
    const prevFiles = files;
    const newFiles = [];
    for (let i = 0; i < prevFiles.length; i += 1) {
      const file = prevFiles[i];
      const { webkitRelativePath } = prevFiles[i];
      const folderName = webkitRelativePath.split('/')[0];
      if (folderName !== name) {
        newFiles.push(file);
      }
    }

    const newFolders = [
      ...folders.slice(0, idx),
      ...folders.slice(idx + 1, folders.length),
    ];

    const validate = checkValidate('files', newFiles);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }

    setFiles(newFiles);
    setFolders(newFolders);
  };

  // URL 컴포넌트 렌더링 함수
  const renderDataInput = () => {
    return (
      <DataInputForm
        files={files}
        folders={folders}
        filesError={filesError}
        uploadTypeOptions={uploadTypeOptions}
        uploadType={uploadType}
        fileInputHandler={fileInputHandler}
        folderInputHandler={folderInputHandler}
        radioBtnHandler={radioBtnHandler}
        onRemoveFiles={onRemoveFiles}
        onRemoveFolder={onRemoveFolder}
      />
    );
  };

  const result = useMemo(
    () => ({
      files,
      folders,
      filesError,
      isValid: filesError === '',
      uploadType,
    }),
    [files, folders, filesError, uploadType],
  );

  return [result, renderDataInput];
};

export default useDataInput;
