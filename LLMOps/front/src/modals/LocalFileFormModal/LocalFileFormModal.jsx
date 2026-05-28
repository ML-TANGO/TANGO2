import { useDispatch } from 'react-redux';
import { sliceUploader } from '@src/fileUpload';

// Actions
import {
  addUploadInstance,
  deleteLastUploadInstance,
  openUploadList,
} from '@src/store/modules/upload';

// Custom Hooks
import useDataInput from './hooks/useDataInput';

// Components
import LocalFileFormModalContent from '@src/components/modalContents/LocalFileFormModalContent';

// Network
import { toast } from '@src/components/Toast';
import { extractPath } from '@src/utils';
import { upload } from '@src/network';

function LocalFileFormModal({ type, data: modalData }) {
  const dispatch = useDispatch();
  const [dataState, renderDataInputForm] = useDataInput();

  const isValidate = dataState.isValid;

  // 분할 업로드
  const splitUpload = (datasetId, form, files, callback) => {
    const uploadInstance = sliceUploader({
      uploadGroupName: form.get('dataset_name'),
      data: files,
      doneFunc: callback,
      uploadRequest: async (s, e, chunk, fileName, fileSize, basePath) => {
        form.set('doc', chunk, basePath ? `${basePath}/${fileName}` : fileName);

        const response = await upload({
          url: `datasets/${datasetId}/files`,
          method: 'put',
          form,
          header: {
            'Content-Range': `bytes ${s}-${e}/${fileSize}`,
          },
        });

        const { status, message } = response;
        if (status === 'STATUS_SUCCESS') {
          return { status: 'STATUS_SUCCESS' };
        }
        toast.error(message);
        return { status: 'STATUS_FAIL', message };
      },
    });

    // 업로드 인스턴스 목록에 추가
    dispatch(addUploadInstance(uploadInstance));

    // 업로드
    const response = uploadInstance.upload();
    if (response) {
      response.then((isUpload) => {
        if (isUpload === false) {
          dispatch(deleteLastUploadInstance());
        }
      });
    }

    // 업로드 목록 모달 열기
    dispatch(openUploadList());
  };

  const onSubmit = async (callback) => {
    const { files: doc, folders, uploadType } = dataState;
    const {
      datasetId,
      loc,
      workspaceId,
      workspaceName,
      datasetName,
      fileType,
    } = modalData;
    const form = new FormData();
    form.append('dataset_id', datasetId);
    if (extractPath(loc)) form.append('path', extractPath(loc));
    // form.append('workspace_id', workspaceId);
    // form.append('workspace_name', workspaceName);
    // form.append('dataset_name', datasetName);
    // form.append('type', uploadType);
    if (Number(uploadType === 0)) {
      if (fileType === 'array') {
        doc.forEach(({ name: fileName }) =>
          form.append('upload_list', fileName),
        );
      } else {
        const fileNameList = doc.map(({ name: fileName }) => fileName);
        form.append('upload_list', fileNameList);
      }
    } else if (Number(uploadType) === 1) {
      if (fileType === 'array') {
        folders.forEach((folderName) => form.append('upload_list', folderName));
      } else {
        form.append('upload_list', folders);
      }
    }

    splitUpload(datasetId, form, doc, callback);
    return true;
  };

  return (
    <LocalFileFormModalContent
      type={type}
      modalData={modalData}
      renderDataInputForm={renderDataInputForm}
      isValidate={isValidate}
      onSubmit={onSubmit}
    />
  );
}

export default LocalFileFormModal;
