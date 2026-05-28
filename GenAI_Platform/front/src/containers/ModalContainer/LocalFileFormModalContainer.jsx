import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import Cookies from 'universal-cookie';

import LocalFileFormModal from '@src/components/Modal/LocalFileFormModal';
// Components
import { toast } from '@src/components/Toast';

// Actions
import {
  addUploadInstance,
  deleteLastUploadInstance,
  openUploadList,
} from '@src/store/modules/upload';

// Network
import { callApi, STATUS_SUCCESS, upload } from '@src/network';
import { errorToastMessage, extractPath } from '@src/utils';

const workerScript = new URL('./uploadWorker.js', import.meta.url);

function LocalFileFormModalContainer(props) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  // Component State
  const [files, setFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [filesError, setFilesError] = useState();
  const [uploadType, setUploadType] = useState(0);
  const uploadTypeOptions = [
    { label: 'file.label', value: 0 },
    { label: 'folder.label', value: 1 },
  ];
  const [footerMessage, setFooterMessage] = useState('');
  const [uploadPath, setUploadPath] = useState('');
  const [fileNames, setFileNames] = useState([]);
  const [folderNames, setFolderNames] = useState([]);
  const [uploadLoading, setUploadLoading] = useState(false);

  const textInputHandler = (e) => {
    setUploadPath(e.target.value);
  };

  useEffect(() => {
    const MAX_SIZE = 100 * 1024 * 1024; // 100MB in bytes
    if (uploadType === 0) {
      if (!files.length) {
        setFooterMessage(`${t('datasetFileUpload.error.message')}`);
      } else {
        let totalSize = 0;

        for (let i = 0; i < files.length; i++) {
          totalSize += files[i].size;
        }

        if (totalSize > MAX_SIZE) {
          // setFooterMessage(`${t('datasetFileSize.error.message')}`);
          // setFilesError(`${t('datasetFileSize.error.message')}`);
        } else {
          setFooterMessage('');
          setFilesError('');
        }
      }
      return;
    }

    if (uploadType === 1) {
      if (!folders.length) {
        setFooterMessage(`${t('datasetFolderUpload.error.message')}`);
      } else {
        let totalSize = 0;

        for (let i = 0; i < files.length; i++) {
          totalSize += files[i].size;
        }

        if (totalSize > MAX_SIZE) {
          // setFooterMessage(`${t('datasetFileSize.error.message')}`);
          // setFilesError(`${t('datasetFileSize.error.message')}`);
        } else {
          setFooterMessage('');
          setFilesError('');
        }
      }
      return;
    }

    setFooterMessage('');
  }, [uploadType, files, folders]);

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
  const fileInputHandler = async (newFiles) => {
    console.log('AAAAAAAA');

    const {
      datasetId,
      loc,
      workspaceId,
      workspaceName,
      datasetName,
      fileType,
    } = props.data;

    const prevFiles = files;
    const fileList = [...prevFiles, ...newFiles];

    setFiles(fileList);
    const names = fileList.map((file) => file.name);

    const body = {
      dataset_id: datasetId,
      data_list: names,
    };

    if (extractPath(loc)) {
      body.path = extractPath(loc);
    }

    // 파일 이름을 업데이트한 리스트를 저장할 변수 선언
    let updatedFileList = fileList;

    // 백엔드로 파일 이름 전송
    const response = await callApi({
      url: 'upload/check',
      method: 'post',
      body,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { result: resData } = result;
      const updatedNames = resData;

      // 파일 이름 업데이트
      updatedFileList = fileList.map((file) => {
        const newName = updatedNames[file.name] || file.name; // 바뀐 이름을 적용
        return new File([file], newName, {
          type: file.type,
          lastModified: file.lastModified,
        });
      });

      setFiles(updatedFileList);
    }

    const validate = checkValidate('files', fileList);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }
  };
  // 인풋 파일(폴더) 이벤트 핸들러
  // const folderInputHandler = (newFiles) => {
  //   // ! 폴더 등록하는 순간
  //   console.log('BBBBB');
  //   const prevFiles = files;
  //   const fileList = [...prevFiles, ...newFiles];
  //   const folderNameList = [];
  //   for (let i = 0; i < fileList.length; i += 1) {
  //     const { webkitRelativePath } = fileList[i];
  //     const folderName = webkitRelativePath.split('/')[0];
  //     // eslint-disable-next-line no-continue
  //     if (folderNameList.indexOf(folderName) > -1) continue;

  //     folderNameList.push(folderName);
  //   }
  //   setFiles(fileList);
  //   setFolders(folderNameList);

  //   const validate = checkValidate('files', fileList);
  //   if (validate) {
  //     setFilesError(validate);
  //   } else {
  //     setFilesError('');
  //   }
  // };

  const folderInputHandler = async (newFiles) => {
    console.log('BBBBB');
    const {
      datasetId,
      loc,
      workspaceId,
      workspaceName,
      datasetName,
      fileType,
    } = props.data;

    const prevFiles = files;
    const fileList = [...prevFiles, ...newFiles];
    const folderNameList = [];

    for (let i = 0; i < fileList.length; i += 1) {
      const { webkitRelativePath } = fileList[i];
      const folderName = webkitRelativePath.split('/')[0];
      if (folderNameList.indexOf(folderName) > -1) continue;

      folderNameList.push(folderName);
    }

    console.log('파일 객체 1 : ', fileList);
    setFiles(fileList);
    setFolders(folderNameList);

    const body = {
      dataset_id: datasetId,
      data_list: folderNameList,
    };

    if (extractPath(loc)) {
      body.path = extractPath(loc);
    }

    const response = await callApi({
      url: 'upload/check',
      method: 'post',
      body,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const { result: resData } = result;

      const updatedNames = resData;

      // updatedFileList: 새로운 파일 리스트를 생성하며, 각 파일의 새로운 이름을 설정
      const updatedFileList = fileList.map((file) => {
        const pathParts = file.webkitRelativePath.split('/');
        const folderName = pathParts[0];
        const newFolderName = updatedNames[folderName] || folderName;
        pathParts[0] = newFolderName;
        const newPath = pathParts.join('/');

        // 새 이름으로 새로운 파일 객체 생성
        return new File([file], file.name, {
          type: file.type,
          lastModified: file.lastModified,
        });
      });

      console.log('파일 객체 22 : ', updatedFileList);
      setFiles(updatedFileList);
      setFolders(Object.values(updatedNames));
    }

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

  const postUpload = async ({
    id,
    file,
    folderPath,
    totalFolderSize,
    uploadType,
    callback,
  }) => {
    const {
      datasetId,
      workspaceId,
      workspaceName,
      datasetName,
      fileType,
      getFakeFileList,
      loc,
    } = props.data;

    const formData = new FormData();
    formData.append('dataset_id', id);

    if (extractPath(loc)) {
      formData.append('path', extractPath(loc));
    }

    const sanitizeFileName = (name) => {
      const excludeChars = /[?*<>#$%&(),/"|\\\s]/g;
      return name.replace(excludeChars, '_').normalize('NFC');
    };

    const relativePath = file.webkitRelativePath || file.name;
    const pathParts = relativePath.split('/');
    const originFileName = pathParts.pop();
    const sanitizedFileName = sanitizeFileName(originFileName);

    const newFileName = pathParts.join('/')
      ? `${pathParts.join('/')}/${sanitizedFileName}`
      : sanitizedFileName;

    const newFile = new File([file], sanitizedFileName, {
      type: file.type,
      lastModified: file.lastModified,
    });

    formData.append('files', newFile, newFileName);

    if (uploadType === 0) {
      formData.append('size', file.size); // 개별 파일의 크기
      formData.append('type', 'file');
    } else {
      formData.append('size', totalFolderSize); // 폴더의 총 크기
      formData.append('type', 'dir');
    }

    const fileDetails = [];
    if (folderPath) {
      const folderNamesSet = new Set();
      const folderName = folderPath.split('/')[0];
      if (!folderNamesSet.has(folderName)) {
        folderNamesSet.add(folderName);
        fileDetails.push({
          name: sanitizeFileName(folderName),
          type: 'dir',
          fake: true,
          fakePath: extractPath(loc),
          upload_info: {
            remain_time: null,
            progress: 0,
            total_size: null,
            upload_size: null,
          },
          modifier: '',
          modified: '-',
        });
      }
    }

    fileDetails.push({
      name: newFileName,
      type: 'file',
      fake: true,
      fakePath: extractPath(loc),
      upload_info: {
        remain_time: null,
        progress: 0,
        total_size: null,
        upload_size: null,
      },
      modifier: '',
      modified: '-',
    });

    getFakeFileList(fileDetails);

    const response = await callApi({
      url: 'upload',
      method: 'post',
      isFormData: true,
      body: formData,
    });

    const { status, message } = response;

    if (status === STATUS_SUCCESS) {
      callback();
    } else {
      getFakeFileList([]);
      errorToastMessage({}, message);
    }
  };

  // const worker = new Worker(workerScript); // 웹 워커 미리 생성

  // const onSubmit = async (callback) => {
  //   const { datasetId, loc, fileType } = props.data;
  //   const folderMap = new Map();
  //   setUploadLoading(true);
  //   const cookies = new Cookies();

  //   let rootFolderPath = '';
  //   let totalRootFolderSize = 0;

  //   files.forEach((file) => {
  //     const relativePath = file.webkitRelativePath || file.name;
  //     const pathParts = relativePath.split('/');
  //     const folderPath = pathParts.slice(0, -1).join('/'); // 최상위 폴더 포함한 경로

  //     if (!folderMap.has(folderPath)) {
  //       folderMap.set(folderPath, []);
  //     }
  //     folderMap.get(folderPath).push(file);

  //     // 최상위 폴더 경로 설정
  //     if (!rootFolderPath) {
  //       rootFolderPath = pathParts[0]; // 최상위 폴더 경로 설정
  //     }

  //     // 최상위 폴더 크기 계산
  //     totalRootFolderSize += file.size;
  //   });

  //   // 최상위 폴더와 하위 폴더들의 본연의 크기(폴더 이름 크기)를 빼기
  //   folderMap.forEach((files, folder) => {
  //     const folderName = folder.split('/').pop();
  //     const folderSize = new Blob([folderName]).size;
  //     totalRootFolderSize -= folderSize;
  //   });

  //   const userName = sessionStorage.getItem('user_name');
  //   const token = sessionStorage.getItem('token');
  //   const loginedSession = sessionStorage.getItem('loginedSession');
  //   const accessToken = cookies.get('access_token');

  //   const filesData = [];

  //   for (const [folderPath, folderFiles] of folderMap) {
  //     for (const file of folderFiles) {
  //       const relativePath = file.webkitRelativePath || file.name;
  //       filesData.push({
  //         id: datasetId,
  //         file,
  //         folderPath: relativePath, // 전체 경로 포함
  //         totalFolderSize: totalRootFolderSize, // 최상위 폴더 크기에서 폴더 본연의 크기를 뺀 값
  //         uploadType, // 파일과 폴더를 구분
  //         apiUrl: 'upload',
  //         userName,
  //         token,
  //         loginedSession,
  //         accessToken,
  //         loc,
  //       });
  //     }
  //   }

  //   worker.postMessage({
  //     filesData,
  //   });

  //   worker.onmessage = (event) => {
  //     callback();
  //     console.log(event); // 이벤트 전체 로그
  //     const { type, token, status, result, error } = event.data;

  //     if (type === 'refreshToken') {
  //       console.log('Z-1');
  //       refreshToken(token);
  //     } else if (type === 'resetSession') {
  //       console.log('Z-2');
  //       resetSession();
  //     } else if (status === 'success') {
  //       console.log('Z-3');
  //       callback(result);
  //       callback();
  //     } else if (status === 'complete') {
  //       console.log('Z-4');
  //       setUploadLoading(false);
  //       callback();
  //     } else {
  //       console.log('Z-5');
  //       console.error(`Worker error: ${error}`);
  //     }
  //   };
  // };
  const worker = new Worker(workerScript); // 웹 워커 미리 생성

  const onSubmit = async (callback) => {
    let firstSubmit = true;
    const { datasetId, loc, fileType } = props.data;
    const folderMap = new Map();
    setUploadLoading(true);
    const cookies = new Cookies();

    let rootFolderPath = '';
    let totalRootFolderSize = 0;

    files.forEach((file) => {
      const relativePath = file.webkitRelativePath || file.name;
      const pathParts = relativePath.split('/');
      const folderPath = pathParts.slice(0, -1).join('/'); // 최상위 폴더 포함한 경로

      if (!folderMap.has(folderPath)) {
        folderMap.set(folderPath, []);
      }
      folderMap.get(folderPath).push(file);

      // 최상위 폴더 경로 설정
      if (!rootFolderPath) {
        rootFolderPath = pathParts[0]; // 최상위 폴더 경로 설정
      }

      // 최상위 폴더 크기 계산
      totalRootFolderSize += file.size;
    });

    // 재귀적으로 폴더 경로를 순회하며 폴더 이름 크기 빼기
    const calculateFolderSize = (folderPath) => {
      const folderName = folderPath.split('/').pop();
      const folderSize = new Blob([folderName]).size;
      totalRootFolderSize -= folderSize;

      for (const [key] of folderMap) {
        if (key.startsWith(`${folderPath}/`) && key !== folderPath) {
          calculateFolderSize(key); //  재귀적으로 하위 폴더 계산
        }
      }
    };

    // 최상위 폴더부터 시작하여 모든 하위 폴더 경로에 대해 크기 계산
    calculateFolderSize(rootFolderPath);

    const userName = sessionStorage.getItem('user_name');
    const token = sessionStorage.getItem('token');
    const loginedSession = sessionStorage.getItem('loginedSession');
    const accessToken = cookies.get('access_token');

    const filesData = [];

    for (const [folderPath, folderFiles] of folderMap) {
      for (const file of folderFiles) {
        const relativePath = file.webkitRelativePath || file.name;
        filesData.push({
          id: datasetId,
          file,
          folderPath: relativePath, // 전체 경로 포함
          totalFolderSize: totalRootFolderSize, // 차감된 최상위 폴더 크기를 동일하게 설정
          uploadType, // 파일과 폴더를 구분
          apiUrl: 'upload',
          userName,
          token,
          loginedSession,
          accessToken,
          loc,
        });
      }
    }

    worker.postMessage({
      filesData,
    });

    worker.onmessage = (event) => {
      console.log(event); // 이벤트 전체 로그
      const { type, token, status, result, error } = event.data;

      if (type === 'refreshToken') {
        console.log('Z-1');
        refreshToken(token);
      } else if (type === 'resetSession') {
        console.log('Z-2');
        resetSession();
      } else if (status === 'success') {
        console.log('Z-3', firstSubmit);
        if (firstSubmit) {
          callback();
        }
        firstSubmit = false;
      } else if (status === 'complete') {
        console.log('Z-4');
        setUploadLoading(false);
      } else {
        console.log('Z-5');
        console.error(`Worker error: ${error}`);
      }
    };
  };

  return (
    <LocalFileFormModal
      {...props}
      isValidate={filesError === ''}
      onSubmit={onSubmit}
      fileInputHandler={fileInputHandler}
      folderInputHandler={folderInputHandler}
      radioBtnHandler={radioBtnHandler}
      onRemoveFiles={onRemoveFiles}
      onRemoveFolder={onRemoveFolder}
      files={files}
      folders={folders}
      uploadTypeOptions={uploadTypeOptions}
      uploadType={uploadType}
      footerMessage={footerMessage}
      uploadPath={uploadPath}
      textInputHandler={textInputHandler}
      uploadLoading={uploadLoading}
    />
  );
}
export default LocalFileFormModalContainer;
