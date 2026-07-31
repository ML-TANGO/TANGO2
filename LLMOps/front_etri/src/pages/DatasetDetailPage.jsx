import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useHistory, useLocation, useRouteMatch } from 'react-router-dom';

import Cookies from 'universal-cookie';

import DatasetFileUploadModalContent from '@src/components/Modal/DatasetFileUploadModal/DatasetFileUploadModalContent';
import DatasetFileUploadModalFooter from '@src/components/Modal/DatasetFileUploadModal/DatasetFileUploadModalFooter';
import DatasetFileUploadModalHeader from '@src/components/Modal/DatasetFileUploadModal/DatasetFileUploadModalHeader';
import DatasetFormModalContent from '@src/components/Modal/DatasetFormModal/DatasetFormModalContent';
import DatasetFormModalFooter from '@src/components/Modal/DatasetFormModal/DatasetFormModalFooter';
import DatasetFormModalHeader from '@src/components/Modal/DatasetFormModal/DatasetFormModalHeader';
// Components
import DatasetDetailContent from '@src/components/pageContents/common/DatasetDetailContent';
import { toast } from '@src/components/Toast';

import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
import {
  addWorker,
  removeWorker,
  startDatasetLoading,
  startUploading,
  stopDatasetLoading,
  stopUploading,
} from '@src/store/modules/uploadLoading';
// Hooks
import useComponentDidMount from '@src/hooks/useComponentDidMount';
import useWorkerClose from '@src/hooks/useWorkerClose';
// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import useIntervalParam from '../hooks/useIntervalParam';

// Utils
import {
  defaultSuccessToastMessage,
  errorToastMessage,
  extractPath,
} from '@src/utils';

const API_HOST_ENV = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = API_HOST_ENV
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

const workerScript = new URL('./uploadWorker.js', import.meta.url);

function ReqInstance(promisFunc, name) {
  this.name = name;
  this.result = true;
  this.callback = () => {};
  this.doneFunc = () => {};
  this.init(promisFunc);
}

ReqInstance.prototype.init = async function (promisFunc) {
  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
  while (true) {
    await sleep(1000);
    this.result = await promisFunc();
    this.callback(this.result);
    if (!this.result) break;
    if (this.result?.done) {
      this.doneFunc();
      break;
    }
  }
};

ReqInstance.prototype.setCallback = function (func) {
  this.callback = func;
};
ReqInstance.prototype.setDoneFunc = function (func) {
  this.doneFunc = func;
};

function DatasetDetailPage({ trackingEvent }) {
  const mounted = useRef(false);

  const prevFileListRef = useRef([]);

  const { t } = useTranslation();

  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const location = useLocation();

  const { id: wid, did: datasetId } = match.params;

  const activeStatus = useMemo(
    () => ['running', 'pending', 'failed', 'installing', 'error'],
    [],
  );

  // Redux hooks
  const dispatch = useDispatch();

  let loading = useSelector((state) => state.loading.multiLoading);
  let uploadLoading = useSelector((state) => state.uploadLoading.isUploading);
  const activeWorkers = useSelector(
    (state) => state.uploadLoading.activeWorkers,
  );

  const [progressValue, setProgressValue] = useState(0);
  const [workspaceId, setWorkspaceId] = useState(null);
  const [workspaceName, setWorkspaceName] = useState('');
  const [tree, setTree] = useState([]);
  const [changedFolderName, setChangedFolderName] = useState([]); // 폴더 트리가 서버에서 업데이트 되기 전에 변경된 폴더명 저장
  const [path, setPath] = useState(['']);
  const [pathInputVal, setPathInputVal] = useState('/');
  const [historyVal, setHistoryVal] = useState([
    { path: [''], page: 1, pathInputVal: '/' },
  ]);
  const [switchStatus, setSwitchStatus] = useState('');
  const [historyTmp, setHistoryTmp] = useState([]);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(10);
  const [datasetName, setDatasetName] = useState('');
  const [datasetDesc, setDatasetDesc] = useState('');
  const [dirCount, setDirCount] = useState(-1); // 폴더 전체 개수
  const [totalFileCount, setTotalFileCount] = useState(-1); // 파일 전체 개수
  const [totalSize, setTotalSize] = useState(-1); // 파일 전체 사이즈
  const [accessType, setAccessType] = useState(-1);
  const [fileList, setFileList] = useState([]); // 파일 목록
  const [fileCount, setFileCount] = useState(0); // 현재 경로의 파일수
  const [selectedRows, setSelectedRows] = useState([]); // 테이블에서 체크된 row 목록
  const [browserSwitch, setBrowserSwitch] = useState(false);

  const [uploadModalLoading, setUploadModalLoading] = useState(false);
  const [toggledClearRows, setToggledClearRows] = useState(false); // 해당 값이 바뀔 때 테이블에서 체크된 row 초기화 (모두 체크 해제)
  const [keyword, setKeyword] = useState(''); // 검색 키워드
  const [permissionLevel, setPermissionLevel] = useState(null); // 권한 레벨
  const [pathInputValue, setPathInputValue] = useState('');
  const [worker, setWorker] = useState(null);
  const [prevValueChange, setPrevValueChange] = useState(false);
  const [deletedFiles, setDeletedFiles] = useState([]);
  const [searchKey, setSearchKey] = useState({
    label: t('name.label'),
    value: 'name',
  });
  const [fileType, setFileType] = useState({
    label: t('allType.label'),
    value: 'all',
  });
  const [paginationResetDefaultPage, setPaginationResetDefaultPage] =
    useState(false);
  const [autoLabelingProgress, setAutoLabelingProgress] = useState(null);
  const [downloading, setDownloading] = useState(false); // 다운로드 중
  const [disabledDecompress, setDisabledDecompress] = useState(true); // 압축해제 불가
  const [decompressing, setDecompressing] = useState(false); // 압축해제 중
  const [deleting, setDeleting] = useState(false); // 삭제 중
  const [destinationPath, setDestinationPath] = useState(''); // 이동/복사 경로
  const [newFolder, setNewFolder] = useState(''); // 이동/복사 새폴더
  const [isCopy, setIsCopy] = useState(false); // 복사본 만들기 여부
  const [tableLoading, setTableLoading] = useState(true);
  const [switchLoading, setSwitchLoading] = useState(false);

  const [isFetchingDetail, setIsFetchingDetail] = useState(false);
  const [isFetchingInfo, setIsFetchingInfo] = useState(false);
  const [fakeFileList, setFakeFileList] = useState([]);
  const [rowClickFetching, setRowClickFetching] = useState(false);
  const [fromUploadFetching, setFromUploadFetching] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMethod, setUploadMethod] = useState('general');

  /**
   * Action 브래드크럼
   * @param {String} wid
   * @param {String} title
   */
  const breadCrumbHandler = useCallback(
    (wid, title) => {
      dispatch(
        startPath([
          {
            component: {
              name: t('Dataset'),
              path: `/user/workspace/${wid}/datasets`,
            },
          },
          {
            component: {
              name: title,
            },
          },
        ]),
      );
    },
    [dispatch, t],
  );

  /**
   * 데이터셋 상세 search 조회
   * @returns boolean
   */
  const getSearchData = useCallback(
    async ({ keywordValue, pathData, selectInput, isMount = false } = {}) => {
      if (isMount) setTableLoading(true);
      const newKeywordValue =
        keywordValue || keywordValue === '' ? keywordValue : keyword;
      const { value: searchKeyItem } = selectInput ? selectInput : searchKey;
      const { value: searchType } = selectInput ? selectInput : fileType;

      const searchSize = pathData?.size ? pathData.size : size;
      // let url = `datasets/${datasetId}/files?search_page=${
      //   pathData?.page ? pathData?.page : page
      // }&search_size=${searchSize}&search_value=${newKeywordValue}&search_key=${searchKeyItem}&search_type=${searchType}`;

      let url = `datasets/${datasetId}/files?search_page=${
        pathData?.page ? pathData?.page : page
      }&search_size=${searchSize}&search_value=${newKeywordValue}&search_key=${searchKeyItem}&search_type=${searchType}`;

      if (pathData?.path && extractPath(pathData?.path.join('/'))) {
        url += `&search_path=${extractPath(pathData?.path.join('/'))}`;
      }

      const response = await callApi({
        url,
        method: 'get',
      });

      const { result, message, status, error } = response;

      if (status === STATUS_SUCCESS) {
        const { list: fileList, file_count: fileCount } = result;

        const prevFileList = prevFileListRef.current;
        const prev = JSON.stringify(prevFileList);
        const current = JSON.stringify(fileList);

        let newFileList = [...fileList];

        if (prev !== current) {
          setPrevValueChange(true);

          setFileList(newFileList);
          prevFileListRef.current = newFileList;
        } else {
          setPrevValueChange(false);
        }

        setFileCount(fileCount);
        if (isMount) setTableLoading(false);
        return newFileList;
      }
      if (isMount) setTableLoading(false);
      errorToastMessage(error, message);
      return false;
    },
    [datasetId, fakeFileList, fileType, keyword, page, path, searchKey, size],

    // [datasetId],
  );

  /**
   * API 호출 GET
   * Dataset 정보 조회
   */
  const getDatasetInfo = useCallback(
    async (isMount) => {
      if (isFetchingInfo) return;
      setIsFetchingInfo(true);

      let {
        id: datasetId,
        name: datasetName,
        description: datasetDesc,
        accessType,
        permissionLevel,
        workspaceId,
      } = location?.state || {};

      if (!datasetId) {
        const pathParts = location.pathname.split('/');
        const newWorkspaceId = pathParts[3];
        const newDatasetId = pathParts[5];
        datasetId = newDatasetId;
        workspaceId = newWorkspaceId;
      }

      if (isMount) {
        setDatasetName(datasetName);
        setDatasetDesc(datasetDesc);
        setAccessType(accessType);
        setPermissionLevel(permissionLevel);
        setWorkspaceId(workspaceId);
      }

      const url = `datasets/${datasetId}/files/info`;
      const response = await callApi({
        url,
        method: 'get',
      });

      const { result, message, status, error } = response;
      if (mounted.current) {
        if (status === STATUS_SUCCESS) {
          const {
            name: datasetName,
            description: datasetDesc,
            access: accessType,
            dir_count: dirCount,
            file_count: totalFileCount,
            size,
            permission_level: permissionLevel,
            workspace_id: workspaceId,
            workspace_name: workspaceName,
            autolabeling_progress: autoLabelingProgress,
            filebrowser,
          } = result;
          // access 1 RW / 0 RO

          setBrowserSwitch(activeStatus.includes(filebrowser));
          setSwitchStatus(filebrowser);

          breadCrumbHandler(workspaceId, datasetName);
          setDatasetName(datasetName);
          setDatasetDesc(datasetDesc);
          setAccessType(accessType);
          setDirCount(dirCount);
          setTotalFileCount(totalFileCount);
          setTotalSize(size);
          // 로데시 객체비교
          // prev data 다르면 set
          //

          setPermissionLevel(permissionLevel);
          setWorkspaceId(workspaceId);
          setWorkspaceName(workspaceName);
          setAutoLabelingProgress(autoLabelingProgress);

          setIsFetchingInfo(false);
          return true;
        }
        errorToastMessage(error, message);
        setIsFetchingInfo(false);
        return false;
      }
    },
    [activeStatus, breadCrumbHandler, location?.state, isFetchingInfo],
  );

  /**
   * API 호출 POST
   * Dataset 정보 동기화
   */
  const syncInfo = useCallback(async () => {
    const { id: datasetId } = location.state;

    const url = `datasets/${datasetId}/files/info`;
    const response = await callApi({
      url,
      method: 'post',
    });

    const { message, status, error } = response;

    if (status === STATUS_SUCCESS) {
      return true;
    }
    errorToastMessage(error, message);
    return false;
  }, [location.state]);

  /**
   * DB 스레드의 동기화 작업 완료 여부 확인
   */
  const checkSyncThread = useCallback(
    async (isToastBlock) => {
      // 해당 url 삭제됨
      // const { id: datasetId, workspaceId } = location.state;
      // const url = `datasets/synchronization`;
      // const form = new FormData();
      // form.append('workspace_id', workspaceId);
      // form.append('dataset_id', datasetId);
      // const response = await callApiWithForm({
      //   url,
      //   method: 'PUT',
      //   form,
      // });
      // const { status, message, error } = response;
      // if (status === STATUS_SUCCESS) {
      //   if (!isToastBlock) {
      //     defaultSuccessToastMessage('sync');
      //   }
      //   return true;
      // }
      // errorToastMessage(error, message);
      // return false;
    },
    [location.state],
  );

  /**
   * API 호출 GET
   * Dataset 폴더 경로 조회
   */
  const getDatasetDirList = useCallback(async () => {
    const url = `datasets/${datasetId}/tree`;
    const response = await callApi({
      url,
      method: 'get',
    });
    const { result, message, status, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result.tree) {
        const { tree } = result;

        const newTree = [...tree];
        newTree.unshift('/'); // root 경로 추가
        // newTree.pop(); // dir 개수 삭제
        changedFolderName.forEach((changedInfo) => {
          const { folderLocation, originName, changedName } = changedInfo;
          const loc = folderLocation.split('/').length - 1;
          newTree.forEach((dir, i) => {
            const originDir = dir.split('/');
            if (originDir[loc] === originName) {
              originDir[loc] = changedName;
              newTree[i] = originDir.join('/');
            }
          });
        });
        setTree(newTree);
        return true;
      }
    } else {
      errorToastMessage(error, message);
    }
  }, [changedFolderName, datasetId]);

  /**
   * 페이지 이동 이벤트
   *
   * @param {number} page 페이지 번호
   */
  const onChangePage = async (page) => {
    setRowClickFetching(true);

    const newPage = { size, page, path };

    setPage(page);
    await getDatasetDetail(newPage, keyword, true);

    const currPath = extractPath(path.join('/'));

    function filterFakeList() {
      const fakeNames = fileList.map((item) => item.name);
      return fakeFileList.filter((item) => {
        return !fakeNames.includes(item.name) || item.fakePath !== currPath;
      });
    }

    const newFilteredList = filterFakeList();

    setFakeFileList(newFilteredList);
    setRowClickFetching(false);
    // getDatasetDetail({ page });
  };

  /**
   * 한번에 보여줄 row 갯수 변경
   *
   * @param {number} size 한페이지에 볼 개수
   * @param {number} page 페이지 번호
   */
  const onChangeRowsPerPage = async (size, page) => {
    setRowClickFetching(true);

    setSize(size);
    const newPage = { size, page, path };

    setPage(page);
    await getDatasetDetail(newPage, keyword, true);

    setRowClickFetching(false);
  };

  /**
   * 압축해제 가능 여부 체크
   *
   * @param {object} selectedRows
   */
  const disableDecompression = (selectedRows) => {
    let disabledCount = 0;
    selectedRows.map(({ type, name }) => {
      if (
        type !== 'file' ||
        // 확장자 리스트 .zip, .tar, .tar.gz
        (name.indexOf('.zip') === -1 &&
          name.indexOf('.tar') === -1 &&
          name.indexOf('.tar.gz') === -1)
      ) {
        disabledCount += 1;
      }
      return disabledCount;
    });
    return disabledCount > 0;
  };

  /**
   * 체크박스 선택
   *
   * @param {object} param0 선택된 행
   */
  const onSelect = ({ selectedRows }) => {
    // setDisabledDecompress(disableDecompression(selectedRows));

    // const updatedSelectedRows = selectedRows.filter((row) =>
    //   fileList.some((data) => data.name === row.name),
    // );
    setSelectedRows(selectedRows);
    setDisabledDecompress(disableDecompression(selectedRows));
  };

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
    onSearch('');
  };

  const uploadingData = (status) => {
    setIsUploading(status);
  };

  /**
   * 파일 업로드
   */
  const onFileUpload = () => {
    const loc = `${path.join('/')}/`;

    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Open File Upload Modal',
    });
    dispatch(
      openModal({
        modalType: 'DATASET_UPLOAD',
        modalData: {
          headerRender: DatasetFileUploadModalHeader,
          contentRender: DatasetFileUploadModalContent,
          footerRender: DatasetFileUploadModalFooter,
          submit: {
            text: t('upload.label'),
            func: () => {
              // onDatasetDirUpdate();
              // 제이팍
              dispatch(closeModal('DATASET_UPLOAD'));

              window.sessionStorage.setItem('delete_files', '[]');
              trackingEvent({
                category: 'Dataset File Upload Modal',
                action: 'Upload Dataset File',
              });
            },
          },
          cancel: {
            text: t('cancel.label'),
            func: () => {
              dispatch(closeModal('DATASET_UPLOAD'));
            },
          },
          datasetId,
          loc,
          workspaceName,
          workspaceId,
          datasetName,
          getFakeFileList,
          getFileForUpload,
          fileType: 'array',
          deletedFiles,
          onSubmitUpload,
          uploadModalLoading,

          uploadingData,
          test: () => {
            trackingEvent({
              category: 'Dataset File Upload Modal',
              action: 'Upload Dataset File',
            });
          },
        },
      }),
    );
  };

  const getFakeFileList = (list = []) => {
    setFakeFileList(list);
  };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = (name, value) => {
    if (name === 'searchKey') {
      setSearchKey(value);
    } else if (name === 'fileType') {
      setFileType(value);
    }

    const newPage = { size, page, path };

    getSearchData({ selectInput: value, pathData: newPage });
  };

  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = (value) => {
    setKeyword(value);
    setPage(1);

    const newPage = { size, page, path };
    getDatasetDetail(newPage, value, true);
  };

  /**
   * FileBrowser 스위치 핸들러
   */
  const switchHandler = (value) => {
    setBrowserSwitch(!browserSwitch);
  };

  /**
   * 뒤로가기
   */
  const goBack = () => {
    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Move To Prev Page',
    });
    // history.goBack();
    history.push(`/user/workspace/${wid}/datasets/management`);
  };

  /**
   * 데이터셋 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    // 삭제이치

    //

    //
    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Open Delete Dataset File Confirm Popup',
    });
    dispatch(
      openConfirm({
        title: 'deleteFilePopup.title.label',
        content: 'deleteFilePopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
            trackingEvent({
              category: 'Dataset Detail Page',
              action: 'Delete Dataset File',
            });
          },
        },
        cancel: {
          text: 'cancel.label',
        },
      }),
    );
  };

  /**
   * 데이터셋 정보 수정
   */
  const onUpdate = () => {
    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Open Edit Dataset Modal',
    });

    dispatch(
      openModal({
        modalType: 'EDIT_DATASET',
        modalData: {
          headerRender: DatasetFormModalHeader,
          contentRender: DatasetFormModalContent,
          footerRender: DatasetFormModalFooter,
          submit: {
            text: 'edit.label',
            func: () => {
              onDatasetDirUpdate();
              trackingEvent({
                category: 'Dataset Edit Modal',
                action: 'Edit Dataset',
              });
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: { id: datasetId },
          workspaceId: wid,
        },
      }),
    );
  };

  /**
   * 폴더 생성
   */
  const onCreateFolder = () => {
    const loc = `${path.join('/')}/`;

    dispatch(
      openModal({
        modalType: 'CREATE_FOLDER',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {
              onDatasetDirUpdate();
              trackingEvent({
                category: 'Folder Create Modal',
                action: 'Create Folder',
              });
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: { id: datasetId },
          workspaceId,
          datasetId,
          loc,
          workspaceName,
          datasetName,
          accessType,
        },
      }),
    );
  };
  /**
   * API 호출 GET
   * 데이터셋 상세 데이터 조회
   */
  const getDatasetDetail = useCallback(
    async (pathData, value, mount) => {
      if (isFetchingDetail) return;
      setIsFetchingDetail(true);

      const isSearch = await getSearchData({ keywordValue: value, pathData });
      if (isSearch === false) {
        setIsFetchingDetail(false);
        return;
      }

      if (!mount) {
        const isInfo = await getDatasetInfo(true);
        if (isInfo === false) {
          setIsFetchingDetail(false);
          return false;
        }
      }

      setIsFetchingDetail(false);
    },

    [getDatasetInfo, getSearchData, isFetchingDetail],
  );

  /**
   * 한림대용 DB에서 업로드
   */
  const onDatabaseUpload = async () => {
    const loc = `${path.join('/')}/`;
    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Open Hanlim DB Upload Modal',
    });

    dispatch(
      openModal({
        modalType: 'UPLOAD_HANLIM',
        modalData: {
          submit: {
            text: t('upload.label'),
            func: () => {
              onDatasetDirUpdate();
              trackingEvent({
                category: 'Hanlim DB Upload Modal',
                action: 'Hanlim DB Upload',
              });
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { id: datasetId },
          workspaceId,
          datasetId,
          loc,
          workspaceName,
          datasetName,
          accessType,
        },
      }),
    );

    // const response = await callApi({
    //   url: `datasets/${datasetId}/get_db`,
    //   method: 'get',
    // });

    // const { status, message } = response;

    // if (status === STATUS_SUCCESS) {
    //   defaultSuccessToastMessage('upload');
    // } else {
    //   errorToastMessage({}, message);
    // }
  };

  const handleWorkerReady = (workerInstance) => {
    // 웹 워커 인스턴스를 저장
    setWorker(workerInstance);
  };

  /**
   * 구글드라이브 업로드
   */
  const onGoogleDriveUpload = () => {
    const loc = `${path.join('/')}/`;
    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Open Google Drive Modal',
    });
    dispatch(
      openModal({
        modalType: 'UPLOAD_GOOGLE_DRIVE',
        modalData: {
          submit: {
            text: t('upload.label'),
            func: () => {
              getDatasetDetail();
              trackingEvent({
                category: 'Google Drive Upload Modal',
                action: 'Google Drive Upload',
              });
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { id: datasetId },
          workspaceId,
          datasetId,
          loc,
          workspaceName,
          datasetName,
          accessType,
        },
      }),
    );
  };

  /**
   * GitHub Clone
   */
  const onGitHubClone = () => {
    const loc = `${path.join('/')}/`;

    trackingEvent({
      category: 'Dataset Detail Page',
      action: 'Open Github Clone Modal',
    });
    dispatch(
      openModal({
        modalType: 'CLONE_GITHUB',
        modalData: {
          submit: {
            text: t('clone.label'),
            func: () => {
              getDatasetDetail();
              trackingEvent({
                category: 'Github Clone Modal',
                action: 'Github Clone',
              });
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          data: { id: datasetId },
          workspaceId,
          datasetId,
          loc,
          workspaceName,
          datasetName,
          accessType,
        },
      }),
    );
  };

  /**
   * 파일/폴더 이름 변경
   *
   * @param {object} row 파일/폴더 데이터
   */
  const onUpdateName = (row) => {
    const type = row.type === 'dir' ? 'Folder' : 'File';

    const loc = `${path.join('/')}/`;

    trackingEvent({
      category: 'Dataset Detail Page',
      action: `Open Edit ${type} Modal`,
    });

    dispatch(
      openModal({
        modalType: `EDIT_${type.toUpperCase()}`,
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              getDatasetDetail();
              setToggledClearRows(!toggledClearRows);
              trackingEvent({
                category: `${type} Edit Modal`,
                action: `Edit ${type}`,
              });
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          onChangedFolderName: (folderLocation, originName, changedName) => {
            if (tree.length === 0) {
              setChangedFolderName(
                changedFolderName.length > 0
                  ? [
                      ...changedFolderName,
                      {
                        originName,
                        changedName,
                        folderLocation,
                      },
                    ]
                  : [
                      {
                        originName,
                        changedName,
                        folderLocation,
                      },
                    ],
              );
            } else {
              const loc = folderLocation.split('/').length - 1;
              const newTree = JSON.parse(JSON.stringify(tree));
              newTree.forEach((dir, i) => {
                const originDir = dir.split('/');
                if (originDir[loc] === originName) {
                  originDir[loc] = changedName;
                  newTree[i] = originDir.join('/');
                }
              });
              setTree(newTree);
            }
          },
          data: row,
          datasetId,
          loc,
          workspaceName,
          workspaceId,
          datasetName,
          accessType,
        },
      }),
    );
  };

  function handleFallback(data, files, headers) {
    let fileName = files[0];
    let blob;
    if (files.length === 1) {
      const contentDisposition = headers['content-disposition'];
      if (contentDisposition) {
        const [fileNameMatch] = contentDisposition
          .split(';')
          .filter((str) => str.includes('filename'));
        if (fileNameMatch) {
          [, fileName] = fileNameMatch.replaceAll('"', '').split('filename=');
        }
      }

      blob = new Blob([data], { type: 'application/octet-stream' });
      fileName = `${fileName}.tar`;
    } else {
      blob = new Blob([data], { type: 'application/x-tar' });
      fileName = `[${datasetName}]_${files.length}_files.tar`;
    }
    fileName = addExtensionIfNeeded(fileName, data.type);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    defaultSuccessToastMessage('download');
  }

  function addExtensionIfNeeded(fileName, mimeType) {
    const extensions = {
      'image/jpeg': '.jpg',
      'application/x-tar': '.tar',
      // 필요에 따라 다른 MIME 타입도 추가
    };

    const extension = extensions[mimeType];
    if (extension && !fileName.endsWith(extension)) {
      return `${fileName}${extension}`;
    }
    return fileName;
  }

  const getFileForUpload = () => {
    const newPage = { size, page, path };
    if (!isFetchingDetail) {
      getDatasetDetail(newPage, keyword, true);
    }
  };

  const onFileDownload = async () => {
    setDownloading(true);
    const loc = `${path.join('/')}/`;
    const files = selectedRows.map(({ name }) => name);

    let url = `download?dataset_id=${datasetId}&download_files=${files.join(
      ',',
    )}`;

    if (loc && loc !== '' && loc !== '/') {
      url = `download?dataset_id=${datasetId}&path=${extractPath(
        loc,
      )}&download_files=${files.join(',')}`;
    }
    const response = await network.callApiWithPromise({
      url,
      method: 'get',
      responseType: 'blob',
    });

    const { status, data, headers } = response;

    const mimeToExtension = {
      'application/octet-stream': ['bin'],
      'application/x-tar': ['tar'],
      'application/zip': ['zip'],
      'application/pdf': ['pdf'],
      'application/msword': ['doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        ['docx'],
      'application/vnd.ms-excel': ['xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': [
        'xlsx',
      ],
      'application/vnd.ms-powerpoint': ['ppt'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation':
        ['pptx'],
      'text/plain': ['txt'],
      'text/html': ['html', 'htm'],
      'text/css': ['css'],
      'text/javascript': ['js'],
      'image/jpeg': ['jpeg', 'jpg'],
      'image/png': ['png'],
      'image/gif': ['gif'],
      'image/bmp': ['bmp'],
      'image/webp': ['webp'],
      'audio/mpeg': ['mp3'],
      'audio/wav': ['wav'],
      'video/mp4': ['mp4'],
      'video/x-msvideo': ['avi'],
      'video/x-matroska': ['mkv'],
      'application/json': ['json'],
      'application/xml': ['xml'],
      'application/rtf': ['rtf'],
      'text/csv': ['csv'],
      // 추가적인 MIME 타입 및 매핑
    };

    const extensionToMime = {
      bin: 'application/octet-stream',
      tar: 'application/x-tar',
      zip: 'application/zip',
      pdf: 'application/pdf',
      doc: 'application/msword',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      xls: 'application/vnd.ms-excel',
      xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ppt: 'application/vnd.ms-powerpoint',
      pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      txt: 'text/plain',
      html: 'text/html',
      htm: 'text/html',
      css: 'text/css',
      js: 'text/javascript',
      jpeg: 'image/jpeg',
      jpg: 'image/jpeg',
      png: 'image/png',
      gif: 'image/gif',
      bmp: 'image/bmp',
      webp: 'image/webp',
      mp3: 'audio/mpeg',
      wav: 'audio/wav',
      mp4: 'video/mp4',
      avi: 'video/x-msvideo',
      mkv: 'video/x-matroska',
      json: 'application/json',
      xml: 'application/xml',
      rtf: 'application/rtf',
      csv: 'text/csv',
      // 추가적인 확장자 및 MIME 타입 매핑
    };

    let fileName = files[0];
    let blob;
    if (status === 200) {
      try {
        const { status } = JSON.parse(data);
        if (status === STATUS_SUCCESS) {
          if (files.length === 1) {
            const contentDisposition = headers['content-disposition'];
            if (contentDisposition) {
              const [fileNameMatch] = contentDisposition
                .split(';')
                .filter((str) => str.includes('filename'));
              if (fileNameMatch)
                [, fileName] = fileNameMatch
                  .replaceAll('"', '')
                  .split('filename=');
            }

            // 확장자를 파일 이름에서 추출하여 MIME 타입을 결정
            const fileExtension = fileName.split('.').pop().toLowerCase();
            const mimeType =
              extensionToMime[fileExtension] || response.data.type;
            const extensions = mimeToExtension[mimeType] || ['tar'];
            const correctFileExtension = extensions.includes(fileExtension)
              ? fileExtension
              : extensions[0];

            blob = new Blob([data], { type: mimeType });
            const fileExtensionPattern = new RegExp(
              `\\.(${extensions.join('|')})$`,
              'i',
            );
            if (!fileExtensionPattern.test(fileName)) {
              fileName += `.${correctFileExtension}`;
            }
          } else {
            blob = new Blob([data], { type: 'application/x-tar' });
            fileName = `[${datasetName}]_${files.length}_files.tar`;
          }
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = fileName;
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);
          defaultSuccessToastMessage('download');
        } else {
          toast.error(t('dataset.004.error.message'));
        }
      } catch (_) {
        if (files.length === 1) {
          const contentDisposition = headers['content-disposition'];
          // if (contentDisposition) {
          //   const [fileNameMatch] = contentDisposition
          //     .split(';')
          //     .filter((str) => str.includes('filename'));
          //   if (fileNameMatch)
          //     [, fileName] = fileNameMatch
          //       .replaceAll('"', '')
          //       .split('filename=');
          // }

          // 확장자를 파일 이름에서 추출하여 MIME 타입을 결정

          const fileExtension = fileName.split('.').pop().toLowerCase();
          const mimeType = extensionToMime[fileExtension] || response.data.type;
          const extensions = mimeToExtension[mimeType] || ['tar'];
          const correctFileExtension = extensions.includes(fileExtension)
            ? fileExtension
            : extensions[0];

          blob = new Blob([data], { type: mimeType });
          const fileExtensionPattern = new RegExp(
            `\\.(${extensions.join('|')})$`,
            'i',
          );
          if (!fileExtensionPattern.test(fileName)) {
            fileName += `.${correctFileExtension}`;
          }
        } else {
          blob = new Blob([data], { type: 'application/x-tar' });
          fileName = `[${datasetName}]_${files.length}_files.tar`;
        }
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        defaultSuccessToastMessage('download');
      }
    } else {
      toast.error(t('dataset.004.error.message'));
    }
    setDownloading(false);
  };
  /**
   * API 호출 GET
   * 체크박스 선택 파일 압축해제
   *
   * @returns
   */
  const onDecompressFile = async () => {
    // setDecompressing(true);

    const loc = `${path.join('/')}/`;
    const files = selectedRows.map(({ name }) => name);
    const isSuccessList = Array.from({ length: files.length }, () => true);

    files.map(async (file, idx) => {
      let url = `datasets/decompress?dataset_id=${datasetId}&file=${file}`;
      if (loc !== '' && loc !== '/' && loc) {
        const newPath = loc.replace(/^\//, '');
        url = `datasets/decompress?dataset_id=${datasetId}&path=${newPath}&file=${file}`;
      }
      const response = await callApi({
        url,
        method: 'get',
      });
      const { status, error, message } = response;
      if (status === STATUS_SUCCESS) {
        onDatasetDirUpdate();
      } else {
        isSuccessList[idx] = false;
        errorToastMessage(error, message);
      }
      if (idx === files.length - 1) {
        setToggledClearRows(!toggledClearRows);
        setDecompressing(false);
      }
      return response;
    });

    // const progressList = files.map((file, idx) => {
    //   // if (f.status !== STATUS_SUCCESS) return false;
    //   const progressRate = new ReqInstance(async () => {
    //     if (isSuccessList[idx] === true) {
    //       const response = await callApi({
    //         url: `datasets/decompress?dataset_id=${datasetId}&path=${loc}&file=${file}`,
    //         method: 'get',
    //       });

    //       const { result, status } = response;
    //       // status가 success일때는 계속 확인
    //       if (status === STATUS_SUCCESS) {
    //         if (result >= 100) {
    //           toast.success(`Successfully decompressed the file ${file}.`);
    //           return { title: file, rate: result, done: true };
    //         }
    //         return { title: file, rate: result };
    //       }
    //       return false;
    //     } else {
    //       dispatch(deleteProgressList(file));
    //     }
    //   }, file);

    //   return progressRate;
    // });

    // dispatch(openProgressList(progressList));
  };

  /**
   * 이전 데이터 미리보기
   * @param {number} previewIndex 현재 미리보기 데이터 index
   */
  const showPrevData = (previewIndex) => {
    if (previewIndex === 0) {
      toast.info(t('previewFirstData.message'));
      return;
    }
    const index = previewIndex - 1;
    for (let i = index; i >= 0; i--) {
      if (fileList[i].type === 'file' && fileList[i].is_preview) {
        onPreview(fileList[i].name, i);
        break;
      }
    }
  };

  /**
   * 다음 데이터 미리보기
   * @param {number} previewIndex 현재 미리보기 데이터 index
   */
  const showNextData = (previewIndex) => {
    if (previewIndex === fileList.length - 1) {
      toast.info(t('previewLastData.message'));
      return;
    }
    const index = previewIndex + 1;
    for (let i = index; i < fileList.length; i++) {
      if (fileList[i].type === 'file' && fileList[i].is_preview) {
        onPreview(fileList[i].name, i);
        break;
      }
    }
  };

  /**
   * 파일 미리보기
   *
   * @param {string} name 파일 이름
   */
  const onPreview = async (name, index) => {
    const fileListIndex = index;
    const loc = `${path.join('/')}/`;
    // 데이터를 받아오기 전에 먼저 모달을 띄워서 로딩을 보여준 뒤 데이터가 오면 대체함
    dispatch(
      openModal({
        modalType: 'PREVIEW',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('PREVIEW'));
            },
          },
          index: fileListIndex,
          fileName: name,
          fileType: null,
          previewData: null,
          showPrevData,
          showNextData,
        },
      }),
    );

    let url = `datasets/preview?dataset_id=${datasetId}&file_name=${encodeURIComponent(
      name,
    )}`;

    if (loc && loc !== '/') {
      const removeSlash = (str) => {
        if (str.startsWith('/')) {
          return str.substring(1);
        }
        return str;
      };

      const newLoc = removeSlash(loc);

      url += `&path=${newLoc}`;
    }
    const response = await network.callApiWithPromise({
      url,
      method: 'get',
    });
    const { status, data } = response;
    if (status === 200) {
      if (data.status === 0) {
        errorToastMessage(data.error, data.message);
      } else {
        dispatch(
          openModal({
            modalType: 'PREVIEW',
            modalData: {
              submit: {
                text: 'confirm.label',
                func: () => {
                  dispatch(closeModal('PREVIEW'));
                },
              },
              index: fileListIndex,
              fileName: name,
              fileType: data.result.type,
              previewData: data.result.data,
              showPrevData,
              showNextData,
            },
          }),
        );
      }
    } else {
      toast.error(t('dataset.012.error.message'));
    }
    return false;
  };

  const generatePath = (inputPath) => {
    const splitPath = inputPath.split('/').filter(Boolean); // 빈 문자열 제거
    const result = [];

    let currentPath = [''];
    let currentPathInputVal = '/';

    // 첫 번째 초기값
    result.push({
      page: 1,
      path: currentPath.slice(),
      pathInputVal: currentPathInputVal,
    });

    // 나머지 경로 추가
    splitPath.forEach((segment) => {
      currentPath.push(segment);
      currentPathInputVal += segment + '/';

      result.push({
        page: 1,
        path: currentPath.slice(),
        pathInputVal: currentPathInputVal.slice(0, -1), // 마지막 '/' 제거
      });
    });

    return result;
  };

  /**
   * API 호출 PUT
   * 데이터셋 삭제
   */
  const onDelete = async () => {
    setDeleting(true);

    const form = new FormData();

    const body = {};
    const data_list = []; // data 이름만 ','로 합쳐서 문자열로 보내야된다.
    form.append('dataset_id', datasetId);
    // body.dataset_id = datasetId;

    const loc = `${path.join('/')}/`;

    if (loc && loc !== '' && loc !== '/') {
      body.path = extractPath(loc);
    }

    selectedRows.forEach(({ name }) => {
      data_list.push(name);
    });

    const currPath = extractPath(path.join('/'));

    function filterFake() {
      return fakeFileList.filter((item) => {
        return !data_list.includes(item.name) || item.fakePath !== currPath;
      });
    }

    // await handleDelete(data_list);

    setFakeFileList(filterFake());

    form.append('data_list', data_list);
    body.data_list = data_list;

    onDeleteFiles(datasetId, loc, data_list).then(async () => {
      const response = await callApi({
        url: `datasets/${datasetId}/files`,
        method: 'post',
        body,
      });

      const { status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setToggledClearRows(!toggledClearRows);
        defaultSuccessToastMessage('delete');
        onDatasetDirUpdate();
        dispatch(stopUploading());
      } else {
        errorToastMessage(error, message);
      }
      window.sessionStorage.setItem('delete_files', '[]');
      setDeleting(false);
    });
  };

  /**
   * row 클릭 이벤트
   * 데이터셋 폴더 클릭시 파일 목록으로 이동
   *
   * @param {object} e 클릭한 데이터셋 폴더/파일 데이터
   */
  const onRowClick = async (e) => {
    const { type, name: dir, fake } = e;
    if (type !== 'dir' || isFetchingDetail || isFetchingInfo || fake) return;
    setRowClickFetching(true);
    setToggledClearRows(!toggledClearRows);

    const prevHistory = [...historyVal];

    const newPath = [...path, dir];
    const history = [...prevHistory];
    const pathInputVal = newPath[0] === '/' ? '/' : newPath.join('/');

    history.push({ path: newPath, page: 1, pathInputVal });

    setPage(1);
    setPath(newPath);
    setPathInputVal(pathInputVal);
    setPathInputValue(`${datasetName}${pathInputVal}`); // 이
    setHistoryVal(history);
    setHistoryTmp([]);
    setPaginationResetDefaultPage(!paginationResetDefaultPage);

    const pathData = {
      page: 1,
      path: newPath,
    };

    await getDatasetDetail(pathData);
    setRowClickFetching(false);
  };

  /**
   * 데이터셋 경로 변경 핸들러
   *
   * @param {object} item {label: '', value: ''}
   */
  const pathChangeHandler = (item) => {
    if (rowClickFetching) return;
    const { value } = item;
    setPathHandler(value);
  };

  /**
   * 데이터셋 경로 이벤트 핸들러
   *
   * @param {object} e
   * @returns
   */
  const pathClickHandler = (e) => {
    if (e.key !== 'Enter' || rowClickFetching) return;
    const value = e.target.value;
    setPathHandler(value);
  };

  /**
   * 데이터셋 경로 설정
   *
   * @param {string} path 데이터셋 경로
   */
  const setPathHandler = async (path) => {
    // Enter 시 이용
    if (rowClickFetching) return;
    setRowClickFetching(true);
    setPathInputVal(path === '' ? '/' : path);

    const prevHistory = JSON.parse(JSON.stringify(historyVal));
    const newPath = path.split('/');

    if (newPath[newPath.length - 1] === '') newPath.pop();
    if (newPath.length === 0) newPath.push('/');

    setPath(newPath);

    // history 추가
    const history = [...prevHistory];
    history.push({ path: newPath, page: 1, pathInputVal: newPath.join('/') });

    setHistoryVal(history);
    setHistoryTmp([]);
    setPaginationResetDefaultPage(!paginationResetDefaultPage);

    // 마지막 문자가 '/'가 아니면 추가해줌
    // if (lastChar !== '/') setPathInputVal(pathInputVal);
    // getDatasetDetail();

    await getDatasetDetail({ path: newPath });
    setRowClickFetching(false);
  };

  /**
   * 데이터셋 경로 뒤로 이동
   */
  const historyBack = async () => {
    const prevHistory = JSON.parse(JSON.stringify(historyVal));

    if (prevHistory.length === 1) return;
    setRowClickFetching(true);

    const history = JSON.parse(JSON.stringify(prevHistory));

    const tmpItem = history.pop();

    const newHistoryTmp = [...historyTmp];

    newHistoryTmp.push(tmpItem);

    let { path, page, pathInputVal } = history[history.length - 1];
    if (pathInputVal === '') pathInputVal = '/';

    setPath(path);
    setPage(page);
    setPathInputVal(pathInputVal);
    setHistoryVal(history);
    setHistoryTmp(newHistoryTmp);
    setPaginationResetDefaultPage(!paginationResetDefaultPage);

    const pathData = {
      path,
      page,
    };
    await getDatasetDetail(pathData);

    setRowClickFetching(false);
  };

  /**
   * 데이터셋 경로 앞으로 이동
   */
  const historyForward = async () => {
    const prevHistory = [...historyVal];

    const prevHistoryTmp = [...historyTmp];

    if (prevHistoryTmp.length === 0) return;
    setRowClickFetching(true);
    const history = [...prevHistory];
    const newHistoryTmp = [...prevHistoryTmp];
    const newPath = newHistoryTmp.pop();
    history.push(newPath);

    const { path, page, pathInputVal } = newPath;

    setPath(path);
    setPage(page);
    setPathInputVal(pathInputVal);
    setHistoryVal(history);
    setHistoryTmp(newHistoryTmp);
    setPaginationResetDefaultPage(!paginationResetDefaultPage);

    const pathData = {
      path,
      page,
    };

    await getDatasetDetail(pathData);
    setRowClickFetching(false);
  };

  /**
   * 이동/복사 - 목적 경로 선택 이벤트 핸들러
   *
   * @param {string} path 경로
   */
  const pathSelectHandler = (path) => {
    setDestinationPath(path);
  };

  /**
   * 이동/복사 - 새폴더 입력 이벤트 핸들러
   *
   * @param {*} e 텍스트 인풋 이벤트
   */
  const pathInputHandler = (e) => {
    const path = e.target.value;
    setNewFolder(path);
  };

  /**
   * 이동/복사 - 복사본 만들기 체크박스 이벤트 핸들러
   *
   * @param {object} e 체크박스 이벤트
   */
  const isCopyCheckHandler = (e) => {
    const checked = e.target.checked;
    setIsCopy(checked);
  };

  const handleRowSelected = (state) => {
    setSelectedRows(state.selectedRows);
  };

  const getFilebrowser = async () => {
    // 실행 Button

    const response = await callApi({
      url: `datasets/${datasetId}/filebrowser`,
      method: 'get',
    });

    const { message, status, error, result } = response;

    if (status === STATUS_SUCCESS) {
      // copyToClipboard(result);
      window.open(result, '_blank');
      // toast.success(result);
    } else {
      errorToastMessage(error, message);
    }
  };

  const postFilebrowser = async () => {
    // Switch

    setSwitchLoading(true);

    const response = await callApi({
      url: `datasets/${datasetId}/filebrowser`,
      method: 'post',
      body: {
        active: browserSwitch ? 'off' : 'on',
      },
    });

    const { message, status, error } = response;

    setSwitchLoading(false);

    if (status === STATUS_SUCCESS) {
      // toast.success(
      //   browserSwitch
      //     ? t('stopTool.message', { tool: 'File browser' })
      //     : t('activateTool.message', { tool: 'File browser' }),
      // );
    } else {
      errorToastMessage(error, message);
    }

    // setBrowserSwitch(!browserSwitch);
  };

  /**
   * 데이터셋 이동/복사
   */
  const onConfirmMoveCopy = async () => {
    let destPath = destinationPath;

    if (newFolder !== '') {
      destPath =
        destinationPath !== '/'
          ? `${destinationPath}/${newFolder}`
          : `/${newFolder}`;
    }

    const loc = `${path.join('/')}/`;
    const files = selectedRows.map(({ name }) => name);

    if (destPath.startsWith('/')) {
      destPath = destPath.substring(1);
    }

    const body = {
      dataset_id: Number(datasetId),

      destination_path: destPath,
      items: files,
      is_copy: Number(isCopy),
    };

    if (loc && loc !== '/') {
      const newLoc = loc.replace(/^\//, '');
      body.target_path = newLoc;
    }

    const response = await callApi({
      url: 'datasets/data-handle',
      method: 'post',
      body,
    });

    const { message, status, error } = response;

    if (status === STATUS_SUCCESS) {
      onDatasetDirUpdate();
      defaultSuccessToastMessage('change');
    } else {
      errorToastMessage(error, message);
    }
    // 초기화
    setDestinationPath('');
    setNewFolder('');
    setIsCopy(false);
    setToggledClearRows(!toggledClearRows);
  };

  function sanitizeFilename(filename) {
    // 정규식을 사용하여 특수 문자 및 공백을 _로 대체
    return filename.replace(/[ :?*<>#$%&()/"|\\]/g, '_');
  }

  const onCancelMoveCopy = () => {
    // 초기화
    setDestinationPath('');
    setNewFolder('');
    setIsCopy(false);
  };

  const onSubmitUpload = ({ files, uploadType, checkedFileList }) => {
    // ? 파일과 폴더 관리 로직이 달라서 중복 코드 발생하더라도 분리함
    // ? 폴더일경우 다소 까다로움, 파일별로 갖고있기 때문에 폴더처럼 만들어서 그룹핑할 필요가있음

    const loc = `${path.join('/')}/`;

    dispatch(startUploading());
    setUploadModalLoading(true);
    dispatch(startDatasetLoading());

    const cookies = new Cookies();
    const userName = sessionStorage.getItem('user_name');
    const token = sessionStorage.getItem('token');
    const loginedSession = sessionStorage.getItem('loginedSession');
    const accessToken = cookies.get('access_token');
    let isFirstFile = true;
    let isFirstFileUploadDone = false;
    let fileUploadToken = 0;
    let folderUploadToken = 0;

    if (uploadType === 1) {
      const folderLength = files.length;

      fileUploadToken = folderLength;
    }

    const collectFiles = (fileList, path = '') => {
      const result = [];
      let totalFolderSize = 0;

      // 먼저 전체 폴더 크기를 계산
      fileList.forEach((file) => {
        const relativePath = file.webkitRelativePath || file.name;
        if (relativePath) {
          totalFolderSize += file.size;
        }
      });

      fileList.forEach((file) => {
        const relativePath = path
          ? `${path}/${file.webkitRelativePath || file.name}`
          : file.webkitRelativePath || file.name;

        if (file.isDirectory) {
          // 폴더라면 하위 항목을 읽어와 재귀적으로 처리
          const reader = file.createReader();
          reader.readEntries((entries) => {
            result.push(...collectFiles(entries, relativePath));
          });
        } else {
          // 파일이라면 결과 배열에 추가
          result.push({
            id: datasetId,
            file,
            folderPath: relativePath,
            totalFolderSize: totalFolderSize,
            relativePath,
            uploadType,
            apiUrl: `${API_HOST}upload`,
            userName,
            token,
            loginedSession,
            accessToken,
            loc,
          });
        }
      });

      return result;
    };

    if (uploadType === 1) {
      // 폴더 업로드

      const folderGroups = {};
      // 폴더 그룹핑

      const originFolderGroups = {};
      // 오리지널 폴더()

      // 각 폴더별로 파일을 그룹화
      files.forEach((file) => {
        const topFolderName = sanitizeFilename(
          file.webkitRelativePath.split('/')[0],
        );
        if (!folderGroups[topFolderName]) {
          folderGroups[topFolderName] = [];
        }
        folderGroups[topFolderName].push(file);
      });

      fileUploadToken = Object.keys(folderGroups).length;
      Object.keys(folderGroups).forEach((topFolderName) => {
        let checkedFile;
        let overwrite;
        const filesData = collectFiles(folderGroups[topFolderName]);

        if (filesData.length === 0) {
          console.error(`No files found in the folder ${topFolderName}.`);
          return;
        }

        files.forEach((file) => {
          const topFolderName = file.webkitRelativePath.split('/')[0];
          if (!originFolderGroups[topFolderName]) {
            originFolderGroups[topFolderName] = [];
          }
          originFolderGroups[topFolderName].push(file);
        });

        const originArray = Object.keys(originFolderGroups);

        for (let i = 0; originArray.length > i; i++) {
          if (
            sanitizeFilename(originArray[i]).trim().normalize() ===
            topFolderName.trim().normalize()
          ) {
            checkedFile = checkedFileList.find(
              (item) =>
                item.fileName.trim().normalize() ===
                originArray[i].trim().normalize(),
            );

            if (checkedFile) {
              overwrite = checkedFile.overwrite;
            }
          }
        }

        // 폴더 업로드인 경우 최상위 폴더 이름으로 비교

        const worker = new Worker(workerScript);

        const workerMessage = {
          type: 'startUpload',
          filesData: filesData,
          isFirstFile: isFirstFile,
          folderToken: topFolderName,
        };

        if (typeof overwrite === 'boolean') {
          workerMessage.overwrite = overwrite;
        }

        worker.postMessage(workerMessage);
        isFirstFile = false;

        // ? dispatch(addWorker(topFolderName, worker)); // 각 폴더별로 워커를 저장 이름은 sani사용
        dispatch(addWorker(datasetId, loc, topFolderName, worker));

        worker.onmessage = (event) => {
          const { type, status, fileName, error } = event.data;
          uploadingData(true);
          dispatch(startUploading());

          if (status === 'success') {
            if (!isFirstFileUploadDone) {
              dispatch(closeModal('DATASET_UPLOAD'));
              isFirstFileUploadDone = true;
              dispatch(stopDatasetLoading());
            }
          } else if (status === 'complete') {
            folderUploadToken += 1;

            if (fileUploadToken === folderUploadToken) {
              // 실제 파일 수와 비교
              uploadingData(false);
              dispatch(stopUploading());
              worker.terminate();
              dispatch(removeWorker(datasetId, loc, topFolderName)); // 워커를 종료하고 제거
            }
          } else if (status === 'uploadCanceled') {
            worker.terminate();
            dispatch(removeWorker(datasetId, loc, topFolderName));
          } else {
            console.error(`Worker error for file ${fileName}: ${error}`);
            uploadingData(false);
            dispatch(stopDatasetLoading());
            worker.terminate();
            dispatch(removeWorker(datasetId, loc, topFolderName));
          }
        };
      });

      setUploadModalLoading(false);
    } else {
      // 파일 업로드
      files.forEach((file) => {
        uploadingData(true);
        const worker = new Worker(workerScript);
        const relativePath = file.webkitRelativePath || file.name;
        const pathParts = relativePath.split('/');
        const folderPath = pathParts.slice(0, -1).join('/');

        let checkedFile = checkedFileList.find(
          (item) =>
            item.fileName.trim().normalize() === file.name.trim().normalize(),
        );

        const fileData = {
          id: datasetId,
          file,
          folderPath: relativePath,
          totalFolderSize: file.size,
          uploadType,
          apiUrl: `${API_HOST}upload`,
          userName,
          token,
          loginedSession,
          accessToken,
          loc,
        };

        if (checkedFile) {
          fileData.overwrite = checkedFile.overwrite;
        }

        worker.postMessage({
          type: 'startUpload',
          filesData: [fileData],
          isFirstFile,
          folderToken: uploadType === 1 ? sanitizeFilename(pathParts[0]) : null,
          uploadType,
        });
        isFirstFile = false;

        const fileName = sanitizeFilename(file.name);

        // ??  dispatch(addWorker(fileName, worker));

        dispatch(addWorker(datasetId, loc, fileName, worker));

        worker.onmessage = (event) => {
          const { status, error } = event.data;
          uploadingData(true);
          dispatch(startUploading());

          if (status === 'success') {
            if (!isFirstFileUploadDone) {
              dispatch(closeModal('DATASET_UPLOAD'));
              isFirstFileUploadDone = true;
              dispatch(stopDatasetLoading());
            }
          } else if (status === 'complete') {
            fileUploadToken += 1;
            if (fileUploadToken === files.length) {
              uploadingData(false);
              dispatch(stopUploading());
              worker.terminate();
              dispatch(removeWorker(datasetId, loc, fileName));
            }
          } else if (status === 'uploadCanceled') {
            worker.terminate();
            dispatch(removeWorker(datasetId, loc, fileName));
          } else {
            console.error(`Worker error for file ${file.name}: ${error}`);
            uploadingData(false);
            dispatch(stopDatasetLoading());
            dispatch(removeWorker(datasetId, loc, fileName));
          }
        };
      });

      setUploadModalLoading(false);
    }
  };

  const onDeleteFile = (id, path, fileName) => {
    return new Promise((resolve, reject) => {
      const key = `${id}:${path}:${fileName}`;
      const worker = activeWorkers.get(key); // 리덕스에서 activeWorkers를 가져옴
      if (worker) {
        let timeout = setTimeout(() => {
          // 일정 시간 내에 응답이 없을 경우 강제로 resolve

          worker.terminate(); // 워커 종료
          dispatch(removeWorker(id, path, fileName)); // 리덕스 상태에서 워커 제거
          resolve();
        }, 5000);

        worker.postMessage({ type: 'cancelUpload', fileName });

        worker.onmessage = (event) => {
          if (event.data.status === 'cancelAcknowledged') {
            clearTimeout(timeout); // 타임아웃 클리어
            worker.terminate(); // 워커 종료

            dispatch(removeWorker(id, path, fileName)); // 리덕스 상태에서 워커 제거
            resolve();
          }
        };
      } else {
        dispatch(removeWorker(id, path, fileName)); // 워커가 없는 경우에도 리덕스 상태에서 제거
        resolve(); // 워커가 없을 경우에도 resolve
      }
    });
  };
  // 삭제 함수 프로미스올을 이용하여 한번에 처리 필요
  const onDeleteFiles = (id, path, fileNames) => {
    return Promise.all(
      fileNames.map((fileName) => onDeleteFile(id, path, fileName)),
    );
  };

  const fromUploadAlarm = async () => {
    setFromUploadFetching(true);
    const newPath = location.state?.uploadingPath;
    const newPage = {
      size: 10,
      page: 1,
      path: newPath.split('/'),
    };
    setPath(newPath.split('/'));
    setPathInputVal(newPath);
    setPathInputValue(`${datasetName}${newPath}`);
    const test = generatePath(newPath);
    setHistoryVal(test);

    await getSearchData({ pathData: newPage, isMount: true });

    setFromUploadFetching(false);
  };

  /**
   * 데이터 업로드 후 Dataset dir 내용 업데이트
   */
  const onDatasetDirUpdate = async () => {
    const newPage = { size, page, path };
    getDatasetDetail(newPage, keyword, true);
    await getDatasetDirList();
    setToggledClearRows(!toggledClearRows);
  };

  useComponentDidMount(
    useCallback(async () => {
      await getDatasetInfo(true);
      if (!location.state?.fromUploadAlarm) getSearchData({ isMount: true });
      await getDatasetDirList();
      await checkSyncThread(true);
    }, [checkSyncThread, getDatasetDirList, getDatasetInfo, getSearchData]),
  );

  // usePreventWindowClose(isUploading);

  useWorkerClose(uploadLoading, activeWorkers);

  useEffect(() => {
    loadModalComponent('DATASET_UPLOAD');
    loadModalComponent('EDIT_DATASET');
    loadModalComponent('CREATE_FOLDER');
    loadModalComponent('UPLOAD_HANLIM');
    loadModalComponent('UPLOAD_GOOGLE_DRIVE');
    loadModalComponent('CLONE_GITHUB');
    loadModalComponent('EDIT_FILE');
    loadModalComponent('PREVIEW');
    mounted.current = true;
    window.sessionStorage.setItem('delete_files', '[]');
    return () => {
      mounted.current = false;
    };
  }, []);

  useIntervalParam(() => {
    const newPage = { size, page, path };

    if (!isFetchingDetail && !fromUploadFetching) {
      getDatasetDetail(newPage, keyword, true);
    }
    if (!isFetchingInfo) {
      getDatasetInfo(false);
    }
  }, 1000);

  useEffect(() => {
    if (location.state?.fromUploadAlarm) {
      fromUploadAlarm();
    }
  }, [location.state]);

  return (
    <DatasetDetailContent
      tableLoading={tableLoading}
      workspaceName={workspaceName}
      datasetName={datasetName}
      datasetDesc={datasetDesc}
      dirCount={dirCount}
      fileCount={fileCount}
      totalFileCount={totalFileCount}
      totalSize={totalSize}
      accessType={accessType}
      fileList={fileList}
      toggledClearRows={toggledClearRows}
      keyword={keyword}
      searchKey={searchKey}
      fileType={fileType}
      tree={tree}
      path={path}
      permissionLevel={permissionLevel}
      newFolder={newFolder}
      datasetId={datasetId}
      pathChangeHandler={pathChangeHandler}
      pathClickHandler={pathClickHandler}
      pathInputVal={pathInputVal}
      setPath={setPathHandler}
      refreshLoading={loading[datasetId]}
      onSelect={onSelect}
      onSearch={onSearch}
      onClear={onClear}
      onUpdate={onUpdate}
      onUpdateName={onUpdateName}
      onChangePage={onChangePage}
      onChangeRowsPerPage={onChangeRowsPerPage}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      onTypeChange={(value) => {
        selectInputHandler('fileType', value);
      }}
      goBack={goBack}
      onRowClick={onRowClick}
      downloading={downloading}
      onDecompressFile={onDecompressFile}
      disabledDecompress={disabledDecompress}
      decompressing={decompressing}
      deleting={deleting}
      autoLabelingProgress={autoLabelingProgress}
      historyBack={historyBack}
      paginationResetDefaultPage={paginationResetDefaultPage}
      historyForward={historyForward}
      onFileUpload={onFileUpload}
      onCreateFolder={onCreateFolder}
      onFileDownload={onFileDownload}
      onGoogleDriveUpload={onGoogleDriveUpload}
      onGitHubClone={onGitHubClone}
      onPreview={onPreview}
      // onSync={onSync}
      pathSelectHandler={pathSelectHandler}
      pathInputHandler={pathInputHandler}
      isCopyCheckHandler={isCopyCheckHandler}
      selectedRows={selectedRows}
      destinationPath={destinationPath}
      isCopy={isCopy}
      onConfirmMoveCopy={onConfirmMoveCopy}
      onCancelMoveCopy={onCancelMoveCopy}
      onDatabaseUpload={onDatabaseUpload}
      loc={`${path.join('/')}/`}
      progressValue={progressValue}
      getFilebrowser={getFilebrowser}
      switchHandler={switchHandler}
      postFilebrowser={postFilebrowser}
      browserSwitch={browserSwitch}
      switchLoading={switchLoading}
      switchStatus={switchStatus}
      fakeFileList={fakeFileList}
      isFetchingDetail={isFetchingDetail}
      rowClickFetching={rowClickFetching}
      fromUploadFetching={fromUploadFetching}
    />
  );
}

export default DatasetDetailPage;
