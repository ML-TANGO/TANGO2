import { sliceUploader } from '@src/fileUpload';
import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';

// Components
import UploadCheckpointModalContent from '@src/components/modalContents/UploadCheckpointModalContent';
import { toast } from '@src/components/Toast';

import { addUploadInstance, openUploadList } from '@src/store/modules/upload';

// Network
import { callApi, STATUS_SUCCESS, upload } from '@src/network';

/**
 * 체크포인트 업로드 모달 컴포넌트
 * 모달의 상태 관리 및 이벤트 정의
 * src/containers/ModalContainer/ModalContainer.jsx에서 사용
 * @param {{
 *  type: 'UPLOAD_CHECKPOINT',
 *  data: Object,
 * }} props
 * @returns
 */
function UploadCheckpointModal({ type, data: modalData }) {
  // 다국어
  const { t } = useTranslation();

  // React Router
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  // Redux Hooks
  const dispatch = useDispatch();

  // Component State
  const [fileList, setFileList] = useState([]);
  const [desc, setDesc] = useState('');
  const [model, setModel] = useState(null);
  const [modelOptions, setModelOptions] = useState([]);

  const fileInputHandler = (files) => {
    setFileList(files);
  };

  const removeFile = (i) => {
    setFileList([
      ...fileList.slice(0, i),
      ...fileList.slice(i + 1, fileList.length),
    ]);
  };

  const textInputHandler = (e) => {
    const { name, value } = e.target;
    if (name === 'desc') setDesc(value);
    // else if (name === 'ckpName') setCkpName(value);
  };

  const selectInputHandler = (s) => {
    setModel(s);
  };

  const onSubmit = async (callback) => {
    let folderName;

    if (fileList.length === 0) {
      const form = new FormData();
      form.set('checkpoint_description', desc);
      form.set('workspace_id', workspaceId);
      if (model) form.set('built_in_model_id', model.value);

      const response = await upload({
        url: 'checkpoints',
        method: 'post',
        form,
      });

      const { status, message } = response;
      if (status === STATUS_SUCCESS) {
        callback();
        // toast.success('success');
        return true;
      }
      toast.error(message);
      return false;
    }

    const uploadInstance = sliceUploader({
      uploadGroupName: 'Checkpoints',
      data: fileList,
      doneFunc: callback,
      uploadRequest: async (s, e, chunk, fileName, fileSize, basePath) => {
        const form = new FormData();
        form.set('checkpoint_description', desc);
        form.set('workspace_id', workspaceId);
        if (model) form.set('built_in_model_id', model.value);
        if (folderName) {
          form.set('chunk_folder_name', folderName);
        }
        form.set(
          'checkpoint_files',
          chunk,
          basePath ? `${basePath}/${fileName}` : fileName,
        );
        const response = await upload({
          url: 'checkpoints',
          method: 'post',
          form,
          header: { 'Content-Range': `bytes ${s}-${e}/${fileSize}` },
        });

        const { result, status, message } = response;
        if (status === 'STATUS_SUCCESS') {
          folderName = result.chunk_folder_name;
          return { status: 'STATUS_SUCCESS', result };
        }
        return { status: 'STATUS_FAIL', message };
      },
    });

    dispatch(addUploadInstance(uploadInstance));

    uploadInstance.upload();

    dispatch(openUploadList());

    return true;
  };

  useEffect(() => {
    const getModelList = async () => {
      const response = await callApi({
        url: 'options/checkpoints',
        method: 'get',
      });

      const { result, message, status } = response;

      if (status === STATUS_SUCCESS) {
        const { built_in_model_list: modelList } = result;
        setModelOptions(
          modelList.map((m) => ({ ...m, label: m.name, value: m.id })),
        );
      } else {
        toast.error(message);
      }
    };

    getModelList();
  }, []);

  const isValidate = model !== null;

  return (
    <UploadCheckpointModalContent
      title={t('uploadCheckpoint.label')}
      onSubmit={onSubmit}
      type={type}
      modalData={modalData}
      fileList={fileList}
      desc={desc}
      model={model}
      modelOptions={modelOptions}
      fileInputHandler={fileInputHandler}
      selectInputHandler={selectInputHandler}
      removeFile={removeFile}
      textInputHandler={textInputHandler}
      isValidate={isValidate}
      t={t}
    />
  );
}

export default UploadCheckpointModal;
