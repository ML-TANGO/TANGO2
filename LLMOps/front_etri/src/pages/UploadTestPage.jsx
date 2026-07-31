import { useState } from 'react';

import { upload } from '@src/network';

import { sliceUploader } from '../fileUpload';
import { extractPath } from '@src/utils';
import Folder from '@src/components/molecules/Folder';
import File from '@src/components/molecules/File';

function UploadTestPage() {
  const [files, setFiles] = useState([]);
  // const [folders, setFolders] = useState([]);

  function onUpload() {
    const uploadInstance = sliceUploader({
      currentFileWatch: () => {
        // console.log('file status : ', status);
        // console.group();
        // console.log(`fileName : ${fileName}`);
        // console.log('fileSize :', fileSize);
        // console.log('takenTime : ', takenTime);
        // console.log('uploadedSize:', uploadedSize);
        // console.log(`speed : ${speed}MB/s`);
        // console.log(`averageSpeed : ${averageSpeed}MB/s`);
        // console.log(`remainingTime : ${remainingTime}`);
        // console.groupEnd();
      },
      totalFileWatch: () => {
        // console.log('total file status:', status);
        // console.group();
        // console.log('fileName : ', status.currentUploadFileName);
        // console.log('speed :', status.speed);
        // console.log('fileSize :', status.fileSize);
        // console.groupEnd();
        // console.log('totalRemainingTime : ', status.totalRemainingTime);
      },
      uploadRequest: async (s, e, chunk, fileName, fileSize, basePath) => {
        const formData = new FormData();
        formData.append('dataset_id', 184);
        if (extractPath('/')) formData.append('path', extractPath('/'));
        // formData.append('workspace_id', 10);
        // formData.append('workspace_name', 'test-ws');
        // formData.append('dataset_name', 'chunk-upload-test');
        // formData.append('type', 0);
        // formData.set(
        //   'doc',
        //   chunk,
        //   basePath ? `${basePath}/${fileName}` : fileName,
        // );

        const response = await upload({
          url: 'datasets/184/files',
          method: 'put',
          form: formData,
          header: { 'Content-Range': `bytes ${s}-${e}/${fileSize}` },
        });
        console.log('response: ', response);
        const { status, message } = response;
        if (status === 'STATUS_SUCCESS') {
          return { status: 'STATUS_SUCCESS' };
        }
        return { status: 'STATUS_FAIL', message };
      },
      successFunc: () => {
        console.log('success');
      },
      failFunc: (message) => {
        console.log('fail :', message);
      },
    });
    uploadInstance.upload(files);
  }

  function fileInputHandler(newFiles) {
    setFiles([...files, ...newFiles]);
  }

  // 인풋 폴더 이벤트 핸들러
  const folderInputHandler = (newFolder) => {
    setFiles(newFolder);
  };

  return (
    <div>
      upload test page
      <div>
        <File
          label='File'
          name='files'
          onChange={fileInputHandler}
          value={files}
          // error={filesError}
          btnText='File'
          // onRemove={onRemove}
          // progressRef={progressRef}
          // single
          // disabled={type === 'EDIT_DOCKER_IMAGE'}
        />
      </div>
      <div>
        <Folder
          onChange={(f) => {
            folderInputHandler(f, 1);
          }}
          value={files}
          error={null}
          btnText='folder.label'
          onRemove={() => {
            // onRemoveFolder(1);
          }}
          directory
          disabledErrorText
          folderList={false}
          // progressRefs={progressRefs}
          index={1}
        />
      </div>
      <button onClick={onUpload}>업로드</button>
    </div>
  );
}

export default UploadTestPage;
