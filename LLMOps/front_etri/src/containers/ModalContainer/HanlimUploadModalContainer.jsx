import { useState, useRef } from 'react';

import { useDispatch } from 'react-redux';
import { closeModal } from '@src/store/modules/modal';
import { sliceUploader } from '@src/fileUpload';

import { cloneDeep } from 'lodash';

// i18n
import { useTranslation } from 'react-i18next';
import HanlimUploadModalContent from '@src/components/modalContents/HanlimUploadModalContent/HanlimUploadModalContent';

// Components
import { toast } from '@src/components/Toast';

// Network
import { upload } from '@src/network';

function HanlimUploadModalContainer({ data, type }) {
  const { submit } = data;

  const { t } = useTranslation();
  const timerIdRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [filesError, setFilesError] = useState(null);
  const [loading, setLoading] = useState(false);

  // const getUpload = async (resFileName, callback) => {
  //   const recursionFetcher = async () => {
  //     const response = await upload({
  //       url: `datasets/db_upload?th_name=${resFileName}`,
  //       method: 'get',
  //     });
  //     const { status } = response;

  //     if (status === 'STATUS_SUCCESS') {
  //       setLoading(false);
  //       // dispatch(closeUploadList());
  //       toast.success(t('dataset.db.upload.label'));
  //       callback();
  //       dispatch(closeModal('UPLOAD_HANLIM'));
  //       return 1;
  //     } else {
  //       const timerId = setTimeout(() => {
  //         recursionFetcher();
  //       }, 2000);
  //       timerIdRef.current = timerId;
  //     }
  //   };

  //   const testStatus = await recursionFetcher();
  //   if (testStatus === 1) {
  //     // dispatch(deleteLastUploadInstance());

  //     return 'STATUS_SUCCESS';
  //   } else {
  //     return 'STATUS_FAIL';
  //   }
  // };

  const splitUpload = async (datasetId, form, files, callback) => {
    setLoading(true);
    let resFileName = '';
    const uploadInstance = sliceUploader({
      uploadGroupName: form.get('dataset_name'),
      data: files,
      noDataFolderName: ['owen'],
      uploadRequest: async (s, e, chunk, fileName, fileSize, basePath) => {
        form.set('doc', chunk, basePath ? `${basePath}/${fileName}` : fileName);

        const response = await upload({
          url: `datasets/db_upload`,
          method: 'post',
          form,
          header: {
            'Content-Range': `bytes ${s}-${e}/${fileSize}`,
          },
        });

        const { status, message, result } = response;
        if (status === 'STATUS_SUCCESS') {
          resFileName = result;
          setLoading(false);
          // dispatch(closeUploadList());
          toast.success(t('dataset.db.upload.label'));
          callback();
          dispatch(closeModal('UPLOAD_HANLIM'));
          return { status: 'STATUS_SUCCESS' };
        } else {
          toast.error(message);
          return { status: 'STATUS_FAIL', message };
        }
      },
    });

    await uploadInstance.upload();

    // getUpload(resFileName, callback);
  };

  // 유효성 검증
  const validateFunc = (name, value) => {
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
  const fileInputHandler = (newFile) => {
    const newFiles = [...newFile];

    let newFilesError = null;

    const validate = validateFunc('files', newFiles);
    if (validate) {
      newFilesError = validate;
    } else {
      newFilesError = '';
    }

    setFilesError(newFilesError);
    setFiles(newFiles);
  };

  // 인풋 파일 삭제 이벤트 핸들러
  const onRemoveFiles = (idx) => {
    const file = cloneDeep(files);

    const newFiles = [
      ...file.slice(0, idx),
      ...file.slice(idx + 1, file.length),
    ];

    let newFilesError = null;

    const validate = validateFunc('files', newFiles);
    if (validate) {
      newFilesError = validate;
    } else {
      newFilesError = '';
    }

    setFiles(newFiles);
    setFilesError(newFilesError);
  };

  const onSubmit = async (callback) => {
    const doc = cloneDeep(files);
    const {
      datasetId,
      loc,
      workspaceId,
      accessType,
      workspaceName,
      datasetName,
    } = data;
    const form = new FormData();
    form.append('dataset_id', datasetId);
    // form.append('path', loc);
    form.append('workspace_id', workspaceId);
    // form.append('workspace_name', workspaceName);
    form.append('dataset_name', datasetName);
    form.append('access', accessType);
    form.append('path', loc);
    form.append('type', 0);
    if (Array.isArray(doc)) {
      files.forEach(({ name: fileName }) =>
        form.append(`upload_list`, fileName),
      );
    } else {
      const fileNameList = files.map(({ name: fileName }) => fileName);
      form.append('upload_list', fileNameList);
    }
    for (let i = 0; i < doc.length; i += 1) {
      // safari에서 폴더 경로 인식을 못함 formdata에 넣을 때 세번째 파라미터로 경로 및 파일명 지정
      // 지우지마세요!!
      const { webkitRelativePath, name: fileName } = doc[i];
      if (!doc[i].prev) {
        form.append('doc', doc[i], webkitRelativePath || fileName);
      }
    }

    splitUpload(datasetId, form, files, callback);
    return true;
  };

  const dispatch = useDispatch();
  return (
    <HanlimUploadModalContent
      // data={data}
      title={t('databaseUpload.title.label')}
      modalData={{
        submit: { text: '업로드', func: submit.func },
        cancel: {
          text: t('cancel.label'),
          func: () => {
            clearTimeout(timerIdRef.current);
            dispatch(closeModal('UPLOAD_HANLIM'));
          },
        },
      }}
      onSubmit={onSubmit}
      fileInputHandler={fileInputHandler}
      isValidate={filesError === ''}
      loading={loading}
      files={files}
      filesError={filesError}
      onRemoveFiles={onRemoveFiles}
    />
  );
}

export default HanlimUploadModalContainer;
