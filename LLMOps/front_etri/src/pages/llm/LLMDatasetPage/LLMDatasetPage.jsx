import { Badge } from '@tango/ui-react';

import { convertLocalTime } from '@src/datetimeUtils';
import { loadModalComponent } from '@src/modal';
import editIcon from '@src/static/images/icon/00-ic-basic-pen.svg';
import syncIcon from '@src/static/images/icon/00-ic-basic-renew.svg';
import downloadIcon from '@src/static/images/icon/00-ic-data-download.svg';
// Icon
import loadingIcon from '@src/static/images/icon/spinner-1s-58.svg';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import MarkerBtn from '@src/components/atoms/MarkerBtn';
import DatasetFormModalContent from '@src/components/Modal/DatasetFormModal/DatasetFormModalContent';
import DatasetFormModalFooter from '@src/components/Modal/DatasetFormModal/DatasetFormModalFooter';
import DatasetFormModalHeader from '@src/components/Modal/DatasetFormModal/DatasetFormModalHeader';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
// Components
import UserDatasetContent from '@src/components/pageContents/user/UserDatasetContent';
import { toast } from '@src/components/Toast';

import { startPath } from '@src/store/modules/breadCrumb';
import { closeConfirm, openConfirm } from '@src/store/modules/confirm';
import {
  closeDownloadProgress,
  openDownloadProgress,
  setDownloadProgress,
} from '@src/store/modules/download';
import {
  closeMultiLoading,
  openMultiLoading,
} from '@src/store/modules/loading';
// Actions
import { openModal } from '@src/store/modules/modal';

// Network
import {
  callApi,
  callApiWithForm,
  download,
  STATUS_SUCCESS,
} from '@src/network';
// Utils
import {
  calcBeforeDateTime,
  convertBinaryByte,
  deepCopy,
  defaultSuccessToastMessage,
  errorToastMessage,
  numberWithCommas,
} from '@src/utils';

const IS_MARKER = import.meta.env.VITE_REACT_APP_IS_MARKER === 'true';
const MARKER_VERSION = import.meta.env.VITE_REACT_APP_MARKER_VERSION;
const IS_DOWNLOAD =
  import.meta.env.VITE_REACT_APP_IS_DOWNLOAD_DATASET !== 'false';

function LLMDatasetPage({ trackingEvent }) {
  // Router Hooks
  const history = useHistory();
  const { id: workspaceId } = useParams();

  // Redux Hooks
  const dispatch = useDispatch();

  // Redux states
  const syncLoading = useSelector((root) => root.loading.multiLoading);
  const allLoading = useSelector(
    (root) => root.loading.multiLoading[`workspace_${workspaceId}`],
  );

  const { t } = useTranslation();

  // State
  const [mount, setMount] = useState(false);
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [downloading, setDownloading] = useState(false);
  const [downloadIds, setDownloadIds] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [builtInModalOpen, setBuiltInModalOpen] = useState(false);
  const [builtInModelList, setBuiltInModelList] = useState([]);
  const [accessType, setAccessType] = useState({
    label: t('allAccessType.label'),
    value: 'all',
  });
  const [searchKey, setSearchKey] = useState({
    label: t('datasetName.label'),
    value: 'dataset_name',
  });
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(7);
  /**
   * 검색 필터링
   * @param {string} value 검색할 내용
   */
  const onSearch = useCallback(
    (value) => {
      let tableData = originData;
      if (accessType.value !== 'all') {
        tableData = tableData.filter(
          (item) => Number(item.access) === Number(accessType.value),
        );
      }
      if (value !== '') {
        tableData = tableData.filter((item) =>
          item[searchKey.value].includes(value),
        );
      }
      setKeyword(value);
      setTableData(tableData);
      setTotalRows(tableData.length);
    },
    [accessType.value, originData, searchKey.value],
  );

  /**
   * Dataset페이지 데이터 요청
   * @param {number | undefined} datasetId
   */
  const getDatasetsData = useCallback(async () => {
    const response = await callApi({
      url: `datasets?workspace_id=${workspaceId}`,
      method: 'get',
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      // 현재시간
      const { list: datasetList } = result;

      let datasetLoadingTemp = {};
      if (syncLoading) {
        datasetLoadingTemp = deepCopy(syncLoading);
      }

      datasetList.forEach((dataset, idx) => {
        const {
          modify_time: modifyDateTime,
          update_time: syncDateTime,
          id,
        } = dataset;

        datasetList[idx] = {
          ...datasetList[idx],
          diffTimeSync: syncDateTime,
          diffTimeEdit: modifyDateTime,
        };

        if (!syncLoading[id]) {
          datasetLoadingTemp = {
            ...datasetLoadingTemp,
            [id]: false,
          };
        }
      });

      if (!allLoading) {
        datasetLoadingTemp = {
          ...datasetLoadingTemp,
          [`workspace_${workspaceId}`]: false,
        };
      }

      dispatch(openMultiLoading(datasetLoadingTemp));
      setOriginData(datasetList);
      setTableData(datasetList);
      setTotalRows(result.total);

      setSelectedRows([]);
      if (keyword !== '') onSearch(keyword);
    } else {
      errorToastMessage(error, message);
    }
  }, [allLoading, dispatch, keyword, onSearch, syncLoading, workspaceId]);

  /**
   * dataset download
   * @param {number} datasetId
   * @param {strubg} datasetName
   * 데이터셋 다운로드
   */
  const onDatasetDownload = useCallback(
    async (datasetId, datasetName) => {
      let downloadIdsBucket = [...downloadIds];
      const fileName = [`${datasetName}.tar`];
      downloadIdsBucket.push(datasetId);

      setDownloadIds([...downloadIdsBucket]);
      setDownloading(true);
      dispatch(openDownloadProgress());

      const response = await download({
        url: `download?dataset_id=${datasetId}`,
        method: 'get',
        responseType: 'blob',
        onDownloadProgress: (progress) => {
          dispatch(setDownloadProgress([progress, fileName]));
        },
      });

      const { status, data } = response;

      if (status === 200) {
        try {
          const responseData = await data.text();
          const { status } = JSON.parse(responseData);
          if (status === 1) {
            const blob = new Blob([data], { type: 'application/x-tar' });

            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = fileName[0];
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            // defaultSuccessToastMessage('download');
          } else {
            dispatch(closeDownloadProgress());
            toast.error(t('dataset.004.error.message'));
          }
        } catch (_) {
          // JSON.parse에 실패한다면 파일 다운로드 성공
          const blob = new Blob([data], { type: 'application/x-tar' });

          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = fileName[0];
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);
          // defaultSuccessToastMessage('download');
        }
      } else {
        dispatch(closeDownloadProgress());
        toast.error(t('dataset.004.error.message'));
      }
      const newDownIds = downloadIdsBucket.filter((item) => item !== datasetId);
      setDownloading(newDownIds.length > 0);
      setDownloadIds([...newDownIds]);
    },
    [dispatch, downloadIds, t],
  );

  const builtInTemplateOpen = (templateData, selectedOption) => {
    setBuiltInModalOpen(false);
    onCreate(templateData, selectedOption);
  };

  /**
   * 빌트인모델데이터셋 모달 핸들러
   */
  const builtInModalOpenHandler = async () => {
    if (!builtInModalOpen) {
      const url = `datasets/new_model_template`;

      const response = await callApi({
        url,
        method: 'GET',
      });

      const { result, message, status, error } = response;
      if (status === STATUS_SUCCESS) {
        setBuiltInModelList(result);
      } else {
        errorToastMessage(error, message);
      }
    }
    setBuiltInModalOpen(!builtInModalOpen);
  };

  /**
   * 데이터셋 생성
   */
  const onCreate = async (templateData, selectedOption) => {
    dispatch(
      openModal({
        modalType: 'CREATE_DATASET',
        modalData: {
          headerRender: DatasetFormModalHeader,
          contentRender: DatasetFormModalContent,
          footerRender: DatasetFormModalFooter,
          submit: {
            text: 'create.label',
            func: () => {
              getDatasetsData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceId,
          templateData,
          selectedOption,
        },
      }),
    );
    trackingEvent({
      category: 'User Dataset Page',
      action: 'Open Create Dataset Modal',
    });
  };

  /**
   * 데이터셋 수정
   * @param {object} row 데이터셋 데이터
   */
  const onUpdate = useCallback(
    (row) => {
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
                getDatasetsData();
                trackingEvent({
                  category: 'Dataset Edit Modal',
                  action: 'Edit Dataset',
                });
              },
            },
            cancel: {
              text: 'cancel.label',
            },
            data: row,
            workspaceId,
          },
        }),
      );
      trackingEvent({
        category: 'User Dataset Page',
        action: 'Open Edit Dataset Modal',
      });
    },
    [dispatch, getDatasetsData, trackingEvent, workspaceId],
  );

  /**
   * DB 스레드의 동기화 작업 완료 여부 확인
   * @param {number | undefined} datasetId
   */
  const checkSyncThread = useCallback(
    async (datasetId) => {
      // 해당 url 삭제
      // const url = `datasets/synchronization`;
      // const form = new FormData();
      // form.append('workspace_id', workspaceId);
      // if (datasetId !== undefined) {
      //   form.append('dataset_id', datasetId);
      // }
      // const response = await callApiWithForm({
      //   url,
      //   method: 'PUT',
      //   form,
      // });
      // const { status, message, error } = response;
      // if (status === STATUS_SUCCESS) {
      //   defaultSuccessToastMessage('sync');
      //   return true;
      // }
      // errorToastMessage(error, message);
      // return false;
    },
    [workspaceId],
  );

  /**
   * API 호출 GET
   * Dataset 정보 동기화
   * @param {number} datasetId 데이터셋 아이디
   */
  const syncData = useCallback(async (datasetId) => {
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
  }, []);

  /**
   * dataset 테이블 동기화
   */
  const onSynchronization = useCallback(
    async (datasetId) => {
      if (!syncLoading[datasetId]) {
        // dataset sync 로딩 시작 dispatch
        dispatch(openMultiLoading(datasetId));
      }
      const isSyncRequest = await syncData(datasetId);
      if (isSyncRequest === false) {
        dispatch(closeMultiLoading(datasetId));
        return;
      }
      const isCheckSyncSuccess = await checkSyncThread(datasetId);
      // dataset sync 로딩 종료 dispatch
      if (isCheckSyncSuccess === true) {
        getDatasetsData();
      }
      dispatch(closeMultiLoading(datasetId));
    },
    [syncLoading, syncData, checkSyncThread, dispatch, getDatasetsData],
  );

  /**
   * API 호출 Delete
   * 데이터셋 삭제
   * 체크박스 선택된 데이터 삭제
   */
  const onDelete = async () => {
    const ids = selectedRows.map(({ id }) => id);
    const response = await callApi({
      url: `datasets/${ids.join(',')}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows(!toggledClearRows);
      getDatasetsData();
      // defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
    closeConfirm();
  };

  /**
   * 데이터셋 전체 동기화
   */
  const onAllSync = async () => {
    // 해당 url 삭제됨
    // if (allLoading === false) {
    //   dispatch(openMultiLoading(`workspace_${workspaceId}`));
    //   const url = `datasets/synchronization`;
    //   const form = new FormData();
    //   form.append('workspace_id', workspaceId);
    //   const response = await callApiWithForm({
    //     url,
    //     method: 'POST',
    //     form,
    //   });
    //   const { message, status, error } = response;
    //   if (status === STATUS_SUCCESS) {
    //     const result = await checkSyncThread();
    //     if (result === true) {
    //       getDatasetsData();
    //     }
    //   } else {
    //     errorToastMessage(error, message);
    //   }
    //   dispatch(closeMultiLoading(`workspace_${workspaceId}`));
    // }
  };

  /**
   * 데이터셋 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    trackingEvent({
      category: 'User Dataset Page',
      action: 'Open Delete Dataset Confirm Popup',
    });
    dispatch(
      openConfirm({
        title: 'deleteDatasetPopup.title.label',
        content: 'deleteDatasetPopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
            trackingEvent({
              category: 'User Dataset Page',
              action: 'Delete Dataset',
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
   * 데이터셋 생성 제한 팝업
   *
   * @param {number} total 무료 생성 가능 개수
   */
  const openLimitCreationPopup = (total) => {
    dispatch(
      openConfirm({
        title: 'datasetCreationCautionPopup.title.label',
        content: t('datasetCreationCautionPopup.message').replace(
          '$total',
          total,
        ),
        submit: {
          text: 'confirm.label',
        },
      }),
    );
  };

  /**
   * 체크박스 선택
   *
   * @param {object} param0 선택된 행
   */
  const onSelect = ({ selectedRows }) => {
    setSelectedRows(selectedRows);
  };

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
  };

  /**
   * 데이터셋 폴더 클릭시 파일 목록으로 이동
   *
   * @param {object} data 선택된 데이터셋 정보
   */
  const onRowClick = (data) => {
    const {
      id: datasetId,
      workspace_id: workspaceId,
      dataset_name: name,
      description,
      access,
      permission_level,
    } = data;

    history.push({
      pathname: `/user/workspace/${workspaceId}/llm-datasets/${datasetId}/files`,
      state: {
        id: datasetId,
        name,
        description,
        accessType: access,
        permissionLevel: permission_level,
        workspaceId,
        loc: ['Home', name, 'Files'],
      },
    });

    trackingEvent({
      category: 'User Dataset Page',
      action: 'Move To Dataset Detail Page',
    });
  };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = (name, value) => {
    if (name === 'accessType') {
      setAccessType(value);
    } else if (name === 'searchKey') {
      setSearchKey(value);
    }
  };

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('accessType.label')}
          idx={0}
        />
      ),
      selector: 'access',
      sortable: true,
      minWidth: '124px',
      maxWidth: '144px',
      cell: ({ access }) => {
        if (Number(access) === 0) {
          return t('readOnly.label');
        }
        return t('readAndWrite.label');
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('datasetName.label')}
          idx={1}
        />
      ),
      selector: 'dataset_name',
      minWidth: '140px',
      sortable: true,
      cell: ({
        dataset_name: datasetName,
        auto_labeling_status: autoLabeling,
      }) => {
        let labelTag = '';
        if (autoLabeling === 'in progress') {
          // 오토라벨링 진행중 표시
          labelTag = (
            <Badge
              customStyle={{ marginLeft: '4px' }}
              label='Auto-labeling'
              type='green'
            />
          );
        } else if (autoLabeling === 'finish') {
          // 오토라벨링 완료 표시
          labelTag = (
            <Badge
              customStyle={{ marginLeft: '4px' }}
              label='Auto-labeled'
              type=''
            />
          );
        }
        return (
          <>
            {datasetName}
            {labelTag}
          </>
        );
      },
    },
    // {
    //   name: (
    //     <SortColumn
    //       onClickHandler={clickedIdxHandler}
    //       sortClickFlag={sortClickFlag}
    //       title={t('files.label')}
    //       idx={2}
    //     />
    //   ),
    //   selector: 'file_count',
    //   maxWidth: '100px',
    //   sortable: true,
    //   cell: ({ file_count: fileCount }) => {
    //     return `${numberWithCommas(fileCount)} ${
    //       fileCount > 0 ? 'files' : 'file'
    //     }`;
    //   },
    // },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('creator.label')}
          idx={2}
        />
      ),
      selector: 'owner',
      maxWidth: '140px',
      sortable: true,
    },
    // 추후에 용량 데이터가 들어오면 계산해서 넣어야함.
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('size.label')}
          idx={3}
        />
      ),
      selector: 'size',
      maxWidth: '140px',
      sortable: true,
      cell: ({ size }) => {
        if (!size) return '0 Bytes';
        return convertBinaryByte(size);
      },
    },
    // {
    //   name: t('sync.label'),
    //   minWidth: '84px',
    //   maxWidth: '100px',
    //   cell: ({ id: datasetId }) => (
    //     <img
    //       src={syncLoading[datasetId] ? loadingIcon : syncIcon}
    //       alt='edit'
    //       className='table-icon'
    //       onClick={() => {
    //         onSynchronization(datasetId);
    //       }}
    //     />
    //   ),
    //   button: true,
    // },
    // {
    //   name: (
    //     <SortColumn
    //       onClickHandler={clickedIdxHandler}
    //       sortClickFlag={sortClickFlag}
    //       title={t('synchronizationTime.label')}
    //       idx={4}
    //     />
    //   ),
    //   selector: 'diffTimeSync',
    //   maxWidth: '166px',
    //   sortable: true,
    //   cell: ({ diffTimeSync }) => {
    //     const beforeUpdateTime = calcBeforeDateTime(diffTimeSync);
    //     return t(`before.${beforeUpdateTime.unit}.label`, {
    //       [beforeUpdateTime.unit]: beforeUpdateTime.beforeTime,
    //     });
    //   },
    // },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('modifiedTime.label')}
          idx={4}
        />
      ),
      selector: 'diffTimeEdit',
      maxWidth: '140px',
      sortable: true,
      cell: ({ diffTimeEdit }) => {
        if (!diffTimeEdit) return '-';
        const beforeEditTime = calcBeforeDateTime(diffTimeEdit);
        return t(`before.${beforeEditTime.unit}.label`, {
          [beforeEditTime.unit]: beforeEditTime.beforeTime,
        });
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('createdAt.label')}
          idx={5}
        />
      ),
      selector: 'create_datetime',
      maxWidth: '160px',
      sortable: true,
      cell: ({ create_datetime: date }) => convertLocalTime(date),
    },
    {
      name: t('download.label'),
      minWidth: '64px',
      maxWidth: '64px',
      cell: ({
        id: datasetId,
        dataset_name: datasetName,
        file_count: fileCount,
      }) => (
        <img
          src={
            downloading && downloadIds.includes(datasetId)
              ? loadingIcon
              : downloadIcon
          }
          alt='download'
          className='table-icon'
          style={{
            opacity: fileCount > 0 && IS_DOWNLOAD ? 1 : 0.2,
            width: '28px',
            height: '28px',
          }}
          onClick={() => {
            if (fileCount > 0 && IS_DOWNLOAD)
              onDatasetDownload(datasetId, datasetName);
          }}
        />
      ),
      button: true,
    },
    {
      name: t('edit.label'),
      minWidth: '64px',
      maxWidth: '64px',
      cell: (row) => (
        <img
          src={editIcon}
          alt='edit'
          className='table-icon'
          style={{
            opacity: row.permission_level < 4 ? 1 : 0.2,
          }}
          onClick={() => {
            if (row.permission_level < 4) onUpdate(row);
          }}
        />
      ),
      button: true,
    },
    {
      name: t('annotation.label'),
      minWidth: '140px',
      cell: ({
        dataset_name: datasetName,
        workspace_name: workspaceName,
        id,
        file_count: fileCount,
      }) => (
        <MarkerBtn
          workspaceName={workspaceName}
          datasetId={id}
          datasetName={datasetName}
          disabled={fileCount === 0}
        />
      ),
      button: true,
      omit: !(IS_MARKER && MARKER_VERSION === '1'),
    },
  ];

  /**
   * Action 브래드크럼
   */
  const breadCrumbHandler = () => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Dataset',
            t,
          },
        },
      ]),
    );
  };

  useEffect(() => {
    loadModalComponent('CREATE_DATASET');
  }, []);

  useEffect(() => {
    if (originData.length !== 0) onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessType, searchKey, originData, keyword]);

  useEffect(() => {
    if (mount === false) {
      getDatasetsData();
      setMount(true);
    }
  }, [getDatasetsData, mount]);

  useEffect(() => {
    breadCrumbHandler();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <UserDatasetContent
      onCreate={onCreate}
      columns={columns}
      tableData={tableData}
      keyword={keyword}
      searchKey={searchKey}
      onSearch={onSearch}
      accessType={accessType}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      onAccessTypeChange={(value) => {
        selectInputHandler('accessType', value);
      }}
      downloading={downloading}
      onRowClick={onRowClick}
      totalRows={totalRows}
      toggledClearRows={toggledClearRows}
      deleteBtnDisabled={selectedRows.length === 0}
      onSelect={onSelect}
      onAllSync={onAllSync}
      loading={allLoading}
      onClear={onClear}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      builtInModalOpen={builtInModalOpen}
      builtInModalOpenHandler={builtInModalOpenHandler}
      builtInModelList={builtInModelList}
      builtInTemplateOpen={builtInTemplateOpen}
      onSortHandler={onSortHandler}
      onDownloadRow={onDatasetDownload}
      onEditRow={onUpdate}
      downloadingIds={downloadIds}
    />
  );
}

export default LLMDatasetPage;
