import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import DatasetFileUploadModal from '@src/components/Modal/DatasetFileUploadModal/DatasetFileUploadModal';
import UploadCheckModal from '@src/components/Modal/UploadCheckModal';
// Components
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Actions

// Network
import { callApi, STATUS_SUCCESS, upload } from '@src/network';
// utils
import {
  defaultSuccessToastMessage,
  encrypt,
  errorToastMessage,
  extractPath,
  // errorToastMessage,
  // defaultSuccessToastMessage,
} from '@src/utils';

function DatasetFileUploadModalContainer(props) {
  const { datasetId, onSubmitUpload, uploadModalLoading } = props.data;

  const { t } = useTranslation();
  const dispatch = useDispatch();
  let uploadLoadingState = useSelector(
    (state) => state.uploadLoading.isLoading,
  );

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
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMethod, setUploadMethod] = useState('general');
  const [gitCommend, setGitCommand] = useState('clone');
  const [isValidate, setIsValiDate] = useState(false);
  const [batch, setBatch] = useState(false);
  const [applyToAll, setApplyToAll] = useState(false);
  const [duplicateFiles, setDuplicateFiles] = useState([]);
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [checkedFileList, setCheckedFileList] = useState([]);
  const [checkLoading, setCheckLoading] = useState(false);
  const [fileActions, setFileActions] = useState(
    duplicateFiles.reduce((acc, file) => {
      acc[file] = null; // 초기값 설정 (null: 선택하지 않음, 'copy': 복사본, 'overwrite': 덮어쓰기)
      return acc;
    }, {}),
  );

  const actionMapping = {
    overwrite: true,
    copy: false,
    cancel: null,
  };

  const [showModal, setShowModal] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  const [scpErrorMessage, setScpErrorMessage] = useState('');
  const SCP_ERROR_MESSAGE = {
    path: `${t('folderName.placeholder')}`,
    username: `${t('userID.empty.message')}`,
    password: `${t('password.empty.message')}`,
    ip: `${t('remoteIp.placeholder')}`,
    file_path: `${t('folderName.placeholder')}`,
  };

  const WGET_ERROR_MESSAGE = {
    path: `${t('folderName.placeholder')}`,
    upload_url: `${t('url.placeholder')}`,
  };

  const GIT_ERROR_MESSAGE = {
    url: `${t('gitRepositoryUrl.placeholder')}`,
    id: `${t('id.empty.message')}`,
    password: `${t('password.empty.message')}`,
  };

  const [scpForm, setScpForm] = useState({
    username: '',
    password: '',
    ip: '',
    file_path: '',
  });

  const [scpFormError, setScpFormError] = useState({
    username: '',
    password: '',
    ip: '',
    file_path: '',
  });

  const [wgetForm, setWgetForm] = useState({
    upload_url: '',
  });

  const [wgetFormError, setWgetFormError] = useState({
    upload_url: '',
  });

  const [gitForm, setGitForm] = useState({
    // uploadPath: '',
    url: '',
    disclosure: 'public',
    id: '',
    password: '',
    pullPath: '',
  });

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      // 엔터 키 입력 시 실행할 로직 추가
    }
  };

  const checkInputValue = ({ input = '' }) => {
    const invalidCharacters = /[\/\s!@#$%^&*(),.?":{}|<>]/;
    return invalidCharacters.test(input);
  };

  const handleGitCommand = (value) => {
    setGitCommand(value);
  };

  const handleScpForm = (value, formType) => {
    if (!value) {
      setScpFormError({
        ...scpFormError,
        [formType]: SCP_ERROR_MESSAGE[formType],
      });
    } else {
      setScpFormError({
        ...scpFormError,
        [formType]: '',
      });
    }

    setScpForm({
      ...scpForm,
      [formType]: value,
    });

    if (formType === 'path') {
      //

      if (checkInputValue({ input: value })) {
        setScpErrorMessage('nameRule.message');
      } else {
        setScpErrorMessage('');
      }
    }
  };
  const handleWgetForm = (value, formType) => {
    if (!value) {
      setWgetFormError({
        ...wgetFormError,
        [formType]: WGET_ERROR_MESSAGE[formType],
      });
    } else {
      setWgetFormError({
        ...wgetFormError,
        [formType]: '',
      });
    }

    setWgetForm({
      ...wgetForm,
      [formType]: value,
    });
  };

  const handleGitForm = (value, formType) => {
    setGitForm({
      ...gitForm,
      [formType]: value,
    });
  };

  const checkHandler = (status) => {
    setApplyToAll(status);
  };

  const handleUploadMethod = (value) => {
    setUploadMethod(value);
  };

  const textInputHandler = (e) => {
    setUploadPath(e.target.value);
  };

  const selectGeneral = () => {
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
        setFooterMessage('');
        setFilesError('');
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
        setFooterMessage('');
        setFilesError('');
      }
      return;
    }

    setFooterMessage('');
  };

  useEffect(() => {
    selectGeneral();
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
      // if (fileNameErrorList.length > 0) {
      //   toast.info(
      //     t('fileNameChange.message', {
      //       fileNameList: `${fileNameErrorList.join('\n')}`,
      //     }),
      //   );
      // }
    }
    return null;
  };

  /**
   * 업로드 체크
   */
  const onCheckUpload = () => {
    dispatch(
      openModal({
        modalType: 'UPLOAD_CHECK',
        modalData: {
          submit: {
            text: t('upload.label'),
            func: () => {},
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { id: datasetId },
          type: 'UPLOAD_CHECK',
        },
      }),
    );
  };

  const onRemoveFilesByName = (fileName) => {
    const newFiles = files.filter((file) => file.name !== fileName);
    setFiles(newFiles);

    const validate = checkValidate('files', newFiles);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }
  };

  const openModal = () => {
    setCurrentFileIndex(0); // 처음부터 시작
    setShowModal(true);
  };
  const sendToBackend = (finalActions) => {
    // 백엔드에 전송할 데이터 생성
    const dataToSend = Object.keys(finalActions)
      .filter((file) => finalActions[file] !== null) // 취소된 파일은 제거
      .map((file) => ({
        fileName: file,
        overwrite: finalActions[file], // true, false 값만 포함 (취소된 파일은 제외)
      }));

    setCheckedFileList(dataToSend);
  };

  // const closeCheckModal = (action, name, applyToAll) => {
  //   const actionMapping = {
  //     overwrite: true,
  //     copy: false,
  //     cancel: null,
  //   };

  //   setFileActions((prevActions) => {
  //     let updatedActions = {
  //       ...prevActions,
  //       [name]: actionMapping[action],
  //     };

  //     if (action === 'cancel') {
  //       // 파일 목록에서 해당 파일 삭제
  //       onRemoveFilesByName(name);
  //     }

  //     if (applyToAll) {
  //       // 모든 나머지 파일에 동일한 액션 적용
  //       const remainingFiles = duplicateFiles.slice(currentFileIndex + 1);
  //       remainingFiles.forEach((file) => {
  //         updatedActions[file] = actionMapping[action];
  //         if (action === 'cancel') {
  //           onRemoveFilesByName(file); // 남은 파일들도 삭제
  //         }
  //       });

  //       // 모든 파일 처리 후 모달 종료
  //       setShowModal(false);
  //       sendToBackend(updatedActions);
  //     } else {
  //       // 다음 파일로 이동
  //       if (currentFileIndex < duplicateFiles.length - 1) {
  //         setCurrentFileIndex(currentFileIndex + 1);
  //       } else {
  //         setShowModal(false);
  //         sendToBackend(updatedActions);
  //       }
  //     }

  //     return updatedActions;
  //   });
  // };

  // const closeCheckModal = (action, name, applyToAll) => {
  //   const actionMapping = {
  //     overwrite: true,
  //     copy: false,
  //     cancel: null,
  //   };

  //   setFileActions((prevActions) => {
  //     let updatedActions = {
  //       ...prevActions,
  //       [name]: actionMapping[action],
  //     };

  //     if (action === 'cancel') {
  //       if (uploadType === 0) {
  //         // 파일 삭제
  //         onRemoveFilesByName(name);
  //       } else if (uploadType === 1) {
  //         // 폴더 삭제
  //         onRemoveFolderByName(name);
  //       }
  //     }

  //     if (applyToAll) {
  //       // 모든 나머지 파일에 동일한 액션 적용

  //       const remainingFiles = duplicateFiles.slice(currentFileIndex + 1);

  //       remainingFiles.forEach((file) => {

  //         updatedActions[file] = actionMapping[action];
  //         if (action === 'cancel') {
  //           if (uploadType === 0) {
  //             onRemoveFilesByName(file); // 남은 파일 삭제
  //           } else if (uploadType === 1) {
  //             onRemoveFolderByName(file); // 남은 폴더 삭제
  //           }
  //         }
  //       });

  //       // 모든 파일 처리 후 모달 종료
  //       setShowModal(false);
  //       sendToBackend(updatedActions);
  //     } else {
  //       // 다음 파일로 이동
  //       if (currentFileIndex < duplicateFiles.length - 1) {
  //         setCurrentFileIndex(currentFileIndex + 1);
  //       } else {
  //         setShowModal(false);
  //         sendToBackend(updatedActions);
  //       }
  //     }

  //     return updatedActions;
  //   });
  // };
  // const closeCheckModal = (action, name, applyToAll) => {
  //    // !
  //   const actionMapping = {
  //     overwrite: true,
  //     copy: false,
  //     cancel: null,
  //   };

  //   setFileActions((prevActions) => {
  //     let updatedActions = {
  //       ...prevActions,
  //       [name]: actionMapping[action],
  //     };

  //     let newFiles = [...files];
  //     let newFolders = [...folders];

  //     if (action === 'cancel') {
  //       if (uploadType === 0) {
  //         // 파일 삭제
  //         newFiles = newFiles.filter((file) => file.name !== name);
  //       } else if (uploadType === 1) {
  //         // 폴더 삭제
  //         newFiles = newFiles.filter(
  //           (file) => file.webkitRelativePath.split('/')[0] !== name,
  //         );
  //         newFolders = newFolders.filter((folder) => folder !== name);
  //       }
  //     }

  //     if (applyToAll) {
  //       // 모든 나머지 파일에 동일한 액션 적용
  //       const remainingFiles = duplicateFiles.slice(currentFileIndex + 1);

  //       remainingFiles.forEach((file) => {
  //         updatedActions[file] = actionMapping[action];
  //         if (action === 'cancel') {
  //           if (uploadType === 0) {
  //             // 남은 파일 삭제
  //             newFiles = newFiles.filter((f) => f.name !== file);
  //           } else if (uploadType === 1) {
  //             // 남은 폴더 삭제
  //             const folderName = file;
  //             newFiles = newFiles.filter(
  //               (f) => f.webkitRelativePath.split('/')[0] !== folderName,
  //             );
  //             newFolders = newFolders.filter((folder) => folder !== folderName);
  //           }
  //         }
  //       });

  //       setFiles(newFiles); // 파일 상태 업데이트
  //       setFolders(newFolders); // 폴더 상태 업데이트

  //       // 모든 파일 처리 후 모달 종료
  //       setShowModal(false);
  //       sendToBackend(updatedActions);
  //     } else {
  //       // 다음 파일로 이동
  //       if (currentFileIndex < duplicateFiles.length - 1) {
  //         setCurrentFileIndex(currentFileIndex + 1);
  //         setFiles(newFiles); // 파일 상태 업데이트
  //         setFolders(newFolders); // 폴더 상태 업데이트
  //       } else {
  //         setShowModal(false);
  //         setFiles(newFiles); // 파일 상태 업데이트
  //         setFolders(newFolders); // 폴더 상태 업데이트
  //         sendToBackend(updatedActions);
  //       }
  //     }

  //     return updatedActions;
  //   });
  // };

  const closeCheckModal = (action, name, applyToAll) => {
    const actionMapping = {
      overwrite: true,
      copy: false,
      cancel: null,
    };

    setFileActions((prevActions) => {
      let updatedActions = {
        ...prevActions,
        [name]: actionMapping[action],
      };

      let newFiles = [...files];
      let newFolders = [...folders];

      const removeFolderByName = (folderName) => {
        // 폴더에 속하는 모든 파일 제거
        newFiles = newFiles.filter((file) => {
          const currentFolderName = file.webkitRelativePath.split('/')[0];
          return currentFolderName !== folderName;
        });

        // 폴더 목록에서 해당 폴더 제거
        newFolders = newFolders.filter((folder) => folder !== folderName);

        const validate = checkValidate('files', newFolders);
        if (validate) {
          setFilesError(validate);
        } else {
          setFilesError('');
        }
      };

      if (action === 'cancel') {
        if (uploadType === 0) {
          newFiles = newFiles.filter(
            (file) => file.name.trim().normalize() !== name.trim().normalize(),
          );
          const validate = checkValidate('files', newFiles);
          if (validate) {
            setFilesError(validate);
          } else {
            setFilesError('');
          }
        } else if (uploadType === 1) {
          // 폴더 삭제
          removeFolderByName(name);
        }
      }

      if (applyToAll) {
        // 모든 나머지 파일에 동일한 액션 적용
        const remainingFiles = duplicateFiles.slice(currentFileIndex + 1);

        remainingFiles.forEach((file) => {
          updatedActions[file] = actionMapping[action];
          if (action === 'cancel') {
            if (uploadType === 0) {
              // 남은 파일 삭제
              newFiles = newFiles.filter(
                (f) => f.name.trim().normalize() !== file.trim().normalize(),
              );

              const validate = checkValidate('files', newFiles);
              if (validate) {
                setFilesError(validate);
              } else {
                setFilesError('');
              }
            } else if (uploadType === 1) {
              // 남은 폴더 삭제
              removeFolderByName(file);
            }
          }
        });

        setFiles(newFiles); // 파일 상태 업데이트
        setFolders(newFolders); // 폴더 상태 업데이트

        // 모든 파일 처리 후 모달 종료
        setShowModal(false);
        sendToBackend(updatedActions);
      } else {
        // 다음 파일로 이동
        if (currentFileIndex < duplicateFiles.length - 1) {
          setCurrentFileIndex(currentFileIndex + 1);
          setFiles(newFiles); // 파일 상태 업데이트
          setFolders(newFolders); // 폴더 상태 업데이트
        } else {
          setShowModal(false);
          setFiles(newFiles); // 파일 상태 업데이트
          setFolders(newFolders); // 폴더 상태 업데이트
          sendToBackend(updatedActions);
        }
      }

      return updatedActions;
    });
  };

  // 인풋 파일 이벤트 핸들러
  const fileInputHandler = async (newFiles) => {
    const {
      datasetId,
      loc,
      workspaceId,
      workspaceName,
      datasetName,
      fileType,
      handleWorkerReady,
    } = props.data;
    setApplyToAll(false);

    // 기존 파일 목록
    let prevFiles = files;

    // 새로운 파일 목록
    const newFileNames = newFiles.map((file) => file.name);

    // 중복된 파일 이름을 제거하고, 새로운 파일 목록에서의 파일을 우선적으로 유지
    prevFiles = prevFiles.filter((file) => !newFileNames.includes(file.name));

    // 최종 파일 목록 생성
    const fileList = [...prevFiles, ...newFiles];

    // 상태 업데이트
    setFiles(fileList);

    const names = fileList.map((file) => file.name);
    const currNames = newFiles.map((file) => file.name);

    const body = {
      dataset_id: datasetId,
      data_list: names,
    };

    const checkBody = {
      dataset_id: datasetId,
      data_list: currNames,
    };

    if (extractPath(loc)) {
      body.path = extractPath(loc);
      checkBody.path = extractPath(loc);
    }

    setCheckLoading(true);
    const checkResponse = await callApi({
      url: 'upload/check',
      method: 'post',
      body: checkBody,
    });

    const { status, message, result } = checkResponse;

    if (status === STATUS_SUCCESS) {
      if (result?.length > 0) {
        // 모달 열기
        const keysArray = result.map((obj) => Object.keys(obj)[0]);
        setDuplicateFiles(keysArray);

        openModal();
      }
    }

    setCheckLoading(false);

    const validate = checkValidate('files', fileList);
    if (validate) {
      setFilesError(validate);
    } else {
      setFilesError('');
    }
  };

  // 인풋 파일(폴더) 이벤트 핸들러
  const folderInputHandler = async (newFiles) => {
    setApplyToAll(false);
    const prevFiles = files;
    const fileList = [...prevFiles, ...newFiles];
    const newFileList = [...newFiles];
    const folderNameList = [];

    const currFolderNameList = [];

    for (let i = 0; i < fileList.length; i += 1) {
      const { webkitRelativePath } = fileList[i];
      const folderName = webkitRelativePath.split('/')[0];
      // eslint-disable-next-line no-continue
      if (folderNameList.indexOf(folderName) > -1) continue;

      folderNameList.push(folderName);
    }

    for (let i = 0; i < newFileList.length; i += 1) {
      const { webkitRelativePath } = newFileList[i];
      const folderName = webkitRelativePath.split('/')[0];
      // eslint-disable-next-line no-continue
      if (currFolderNameList.indexOf(folderName) > -1) continue;

      currFolderNameList.push(folderName);
    }

    setFiles(fileList);
    setFolders(folderNameList);

    const checkBody = {
      dataset_id: datasetId,
      data_list: currFolderNameList,
    };

    if (extractPath(loc)) {
      checkBody.path = extractPath(loc);
    }

    setCheckLoading(true);
    const checkResponse = await callApi({
      url: 'upload/check',
      method: 'post',
      body: checkBody,
    });

    const { status, message, result } = checkResponse;

    if (status === STATUS_SUCCESS) {
      if (result?.length > 0) {
        // 모달 열기
        const keysArray = result.map((obj) => Object.keys(obj)[0]);
        setDuplicateFiles(keysArray);

        openModal();
      }
    }

    setCheckLoading(false);

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
    setCheckLoading(false);
    setUploadType(parseInt(value, 10)); // 파일(0) or 폴더(1)
    setFiles([]);
    setFolders([]);
    setFilesError(null);
    setApplyToAll(false);
    setDuplicateFiles([]);
    setCurrentFileIndex(0);
    setCheckedFileList([]);
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

  // ? 파일리스트를 갖고있다
  // ? 전체 api 쏴서 체크한다
  // ? 응답을 받는다.
  // ? 그걸 따로 .. 잠만 언더바로 바꾸지않나
  // ? 아니다 바꾸는 로직 위에 있으면 되겠다
  // ?

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

  const onRemoveFolderByName = (folderName) => {
    const prevFiles = files;
    const newFiles = [];
    // 폴더에 속하는 모든 파일 제거
    for (let i = 0; i < prevFiles.length; i += 1) {
      const { webkitRelativePath } = prevFiles[i];
      const currentFolderName = webkitRelativePath.split('/')[0];
      if (currentFolderName !== folderName) {
        newFiles.push(prevFiles[i]);
      }
    }

    // 폴더 목록에서 해당 폴더 제거
    const folderIdx = folders.indexOf(folderName);
    const newFolders = [
      ...folders.slice(0, folderIdx),
      ...folders.slice(folderIdx + 1, folders.length),
    ];

    // 유효성 검사 및 상태 업데이트
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
      handleWorkerReady,
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

  const {
    headerRender,
    contentRender,
    footerRender,
    cancel,
    submit,
    datasetName,
    loc,
  } = props.data;

  useEffect(() => {
    if (uploadMethod === 'scp') {
      setIsValiDate(Object.values(scpForm).every((v) => v.length > 0));
      const scpInput = ['username', 'password', 'ip', 'file_path'];

      for (const val of scpInput) {
        if (!scpForm[val]) {
          setFooterMessage(SCP_ERROR_MESSAGE[val]);
          return;
        }
      }
    }

    if (uploadMethod === 'wget') {
      setIsValiDate(Object.values(wgetForm).every((v) => v.length > 0));
      const wgetInput = ['upload_url'];

      for (const val of wgetInput) {
        if (!wgetForm[val]) {
          setFooterMessage(WGET_ERROR_MESSAGE[val]);
          return;
        }
      }
    }

    //

    if (uploadMethod === 'git') {
      if (gitCommend === 'clone') {
        // url 체크
        const gitUrlInput = ['url'];
        for (const val of gitUrlInput) {
          if (!gitForm[val]) {
            setFooterMessage(GIT_ERROR_MESSAGE[val]);
            setIsValiDate(false);
            return;
          }
        }
      }

      const { disclosure } = gitForm;

      if (disclosure === 'private') {
        const gitUrlInput = ['id', 'password'];
        for (const val of gitUrlInput) {
          if (!gitForm[val]) {
            setFooterMessage(GIT_ERROR_MESSAGE[val]);
            setIsValiDate(false);
            return;
          }
        }
      }
      setIsValiDate(true);
    }

    if (uploadMethod === 'general') {
      setIsValiDate(true);
      selectGeneral();
      return;
    }

    setFooterMessage('');
  }, [scpForm, wgetForm, uploadMethod, gitForm, gitCommend, uploadType]);

  const onSubmit = async (callback) => {
    if (uploadMethod === 'general') {
      setUploadLoading(true);
      await onSubmitUpload({ files, uploadType, checkedFileList });
      setUploadLoading(false);
    } else {
      const getDataByMethod = (uploadMethod) => {
        // scp, wget, git 별
        switch (uploadMethod) {
          case 'scp':
            return {
              ...scpForm,
              password: encrypt(scpForm.password),
            };
          case 'wget':
            return wgetForm;
          case 'git':
            return {
              path: gitForm.pullPath,
              git_repo_url: gitForm.url,
              git_cmd: gitCommend,
              git_access: gitForm.disclosure,
              git_id: gitForm.id,
              git_access_token: gitForm.password,
            };
          default:
            return {};
        }
      };

      // 데이터 생성 및 요청 본문 구성
      const data = getDataByMethod(uploadMethod);
      const body = {
        dataset_id: datasetId,
        ...data,
      };

      if (extractPath(loc)) {
        body.path = extractPath(loc);
      }
      setUploadLoading(true);
      const response = await callApi({
        url: `upload/${uploadMethod}`,
        method: 'POST',
        body,
      });

      const { status, message, error } = response;

      if (status === STATUS_SUCCESS) {
        defaultSuccessToastMessage('upload');
        // dispatch(closeModal(type));
        setUploadLoading(false);
        callback();
        return;
      }

      errorToastMessage(error, message);
    }
  };

  return (
    <>
      <DatasetFileUploadModal
        {...props}
        // isValidate={filesError === '' && isValidate}
        isValidate={uploadMethod === 'general' ? filesError === '' : isValidate}
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
        checkLoading={checkLoading}
        uploadLoading={uploadLoading || uploadLoadingState || checkLoading}
        uploadMethod={uploadMethod}
        handleUploadMethod={handleUploadMethod}
        datasetName={datasetName}
        handleGitForm={handleGitForm}
        handleGitCommand={handleGitCommand}
        handleScpForm={handleScpForm}
        wgetFormError={wgetFormError}
        scpFormError={scpFormError}
        scpErrorMessage={scpErrorMessage}
        gitForm={gitForm}
        scpForm={scpForm}
        wgetForm={wgetForm}
        gitCommend={gitCommend}
        handleWgetForm={handleWgetForm}
      />
      <UploadCheckModal
        show={showModal}
        onClose={closeCheckModal}
        checked={applyToAll}
        checkHandler={checkHandler}
        fileName={duplicateFiles[currentFileIndex]}
        uploadType={uploadType}
      />
    </>
  );
}
export default DatasetFileUploadModalContainer;
