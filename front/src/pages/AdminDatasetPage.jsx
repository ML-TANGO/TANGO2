import { convertLocalTime } from '@src/datetimeUtils';
import { loadModalComponent } from '@src/modal';
// Icons
import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useHistory } from 'react-router-dom';

import DatasetFormModalContent from '@src/components/Modal/DatasetFormModal/DatasetFormModalContent';
import DatasetFormModalFooter from '@src/components/Modal/DatasetFormModal/DatasetFormModalFooter';
import DatasetFormModalHeader from '@src/components/Modal/DatasetFormModal/DatasetFormModalHeader';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
// Components
import AdminDatasetContent from '@src/components/pageContents/admin/AdminDatasetContent';
// CSS module
import style from '@src/components/pageContents/admin/AdminDatasetContent/AdminDatasetContent.module.scss';
import { toast } from '@src/components/Toast';

import { closeConfirm } from '@src/store/modules/confirm';
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
import { handleOpenPopup } from '@src/store/modules/popupState';

// Network
import { callApi, download, STATUS_SUCCESS } from '@src/network';
// utils
import {
  calcBeforeDateTime,
  convertBinaryByte,
  deepCopy,
  defaultSuccessToastMessage,
  errorToastMessage,
} from '@src/utils';

import classNames from 'classnames/bind';

const IS_DOWNLOAD =
  import.meta.env.VITE_REACT_APP_IS_DOWNLOAD_DATASET !== 'false';

const cx = classNames.bind(style);

function AdminDatasetPage() {
  const { t } = useTranslation();
  const history = useHistory();
  const dispatch = useDispatch();
  let loading = useSelector((state) => state.loading.multiLoading);
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [tableLoading, setTableLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [downloadIds, setDownloadIds] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [accessType, setAccessType] = useState({
    label: t('allAccessType.label'),
    value: 'all',
  });
  const [searchKey, setSearchKey] = useState({
    label: t('datasetName.label'),
    value: 'dataset_name',
  });
  const [keyword, setKeyword] = useState('');
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(6);

  /**
   * 테이블 데이터 컬럼 정의
   */
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
      name: t('datasetName.label'),
      selector: 'dataset_name',
      minWidth: '200px',
      sortable: false,
      format: ({ dataset_name, workspace_name }) => (
        <div className={cx('name-box')}>
          <span className={cx('name')}>{dataset_name}</span>
          <div className={cx('workspace')}>{workspace_name}</div>
        </div>
      ),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('size.label')}
          idx={1}
        />
      ),
      selector: 'size',
      maxWidth: '170px',
      sortable: true,
      cell: ({ size }) => {
        if (!size) return '0 Bytes';
        return convertBinaryByte(size);
      },
    },
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
      maxWidth: '150px',
      sortable: true,
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('synchronizationTime.label')}
          idx={3}
        />
      ),
      selector: 'diffTimeSync',
      maxWidth: '150px',
      sortable: true,
      cell: ({ diffTimeSync }) => {
        if (!diffTimeSync) return '-';
        const beforeUpdateTime = calcBeforeDateTime(diffTimeSync);
        return t(`before.${beforeUpdateTime.unit}.label`, {
          [beforeUpdateTime.unit]: beforeUpdateTime.beforeTime,
        });
      },
    },
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
      sortable: true,
      maxWidth: '150px',
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
      sortable: true,
      maxWidth: '160px',
      cell: ({ create_datetime: date }) => convertLocalTime(date),
    },
    // {
    //   name: t('download.label'),
    //   minWidth: '70px',
    //   maxWidth: '70px',
    //   cell: ({
    //     id: datasetId,
    //     dataset_name: datasetName,
    //     file_count: fileCount,
    //   }) => (
    //     <img
    //       src={
    //         downloading && downloadIds.includes(datasetId)
    //           ? loadingIcon
    //           : downloadIcon
    //       }
    //       alt='download'
    //       className='table-icon'
    //       style={{
    //         opacity: fileCount > 0 && IS_DOWNLOAD ? 1 : 0.2,
    //       }}
    //       onClick={() => {
    //         if (fileCount > 0 && IS_DOWNLOAD)
    //           onDatasetDownload(datasetId, datasetName);
    //       }}
    //     />
    //   ),
    //   button: true,
    // },
    // {
    //   name: t('edit.label'),
    //   minWidth: '64px',
    //   maxWidth: '64px',
    //   cell: (row) => (
    //     <img
    //       className='table-icon'
    //       src={editIcon}
    //       alt='edit'
    //       onClick={() => {
    //         onUpdate(row);
    //       }}
    //     />
    //   ),
    //   button: true,
    // },
  ];

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  /**
   * API 호출 GET
   * 어드민 데이터셋 데이터 가져오기
   * @param {number | undefined} datasetId
   */
  const getDatasetsData = async (refresh = false) => {
    if (!refresh) setTableLoading(true);
    const response = await callApi({
      url: 'datasets',
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const { list: datasetList, total } = result;
      let datasetLoadingTemp = {};
      if (loading) {
        datasetLoadingTemp = deepCopy(loading);
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
        if (!loading[id]) {
          datasetLoadingTemp = {
            ...datasetLoadingTemp,
            [id]: false,
          };
        }
      });

      if (!loading['all']) {
        datasetLoadingTemp = {
          ...datasetLoadingTemp,
          all: false,
        };
      }

      dispatch(openMultiLoading(datasetLoadingTemp));
      setOriginData(datasetList);
      setTableData(datasetList);
      setTotalRows(total);
      setSelectedRows([]);
      if (!refresh) setTableLoading(false);

      // 상세정보에서 넘어 올 경우
      if (history.location.state) {
        const { workspace, user } = history.location.state;
        if (workspace) {
          setKeyword(workspace);
          selectInputHandler('searchKey', {
            label: t('workspace.label'),
            value: 'workspace_name',
          });
        } else if (user) {
          setKeyword(user);
          selectInputHandler('searchKey', {
            label: t('creator.label'),
            value: 'owner',
          });
        }
      }
      if (keyword !== '') onSearch(keyword);
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
    onSearch('');
    history.push({ state: undefined });
  };

  /**
   * 데이터셋 생성
   */
  const onCreate = () => {
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
        },
      }),
    );
  };

  /**
   * 데이터셋 수정
   *
   * @param {object} row 데이터셋 데이터
   */
  const onUpdate = (row) => {
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
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: row,
        },
      }),
    );
  };

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
      defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
    closeConfirm();
  };

  /**
   * 데이터셋 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: t('deleteDatasetPopup.title.label'),
        popupContents: t('deleteDatasetPopup.message'),
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('delete.label'),
        handleSubmit: async () => {
          await onDelete();
        },
      }),
    );
  };

  /**
   * API 호출 GET
   * 데이터셋 다운로드
   *
   * @param {number} datasetId 데이터셋 아이디
   * @param {string} datasetName 데이터셋 이름
   * @returns {blob} tar 압축파일
   */
  const onDatasetDownload = async (datasetId, datasetName) => {
    downloadIds.push(datasetId);
    setDownloading(true);
    setDownloadIds(downloadIds);
    const fileName = [`${datasetName}.tar`];
    openDownloadProgress();
    const response = await download({
      url: `download?dataset_id=${datasetId}`,
      method: 'get',
      responseType: 'blob',
      onDownloadProgress: (progress) => {
        setDownloadProgress([progress, fileName]);
      },
    });

    const { status, data } = response;
    if (status === 200) {
      try {
        const responseData = await data.text();
        const { status, message } = JSON.parse(responseData);
        if (status === 1) {
          const blob = new Blob([data], { type: 'application/x-tar' });
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = fileName[0];
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);
          defaultSuccessToastMessage('download');
        } else {
          dispatch(closeDownloadProgress());
          toast.error(message);
        }
      } catch (_) {
        const blob = new Blob([data], { type: 'application/x-tar' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName[0];
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        defaultSuccessToastMessage('download');
      }
    } else {
      toast.error('Download error');
    }
    const index = downloadIds.indexOf(datasetId);
    downloadIds.splice(index, 1);
    setDownloading(downloadIds.length > 0, ...downloadIds);
  };

  /**
   *
   * @param {number | undefined} datasetId
   * @param {number | undefined} workspaceId
   * @returns
   */
  const checkSyncThread = async (datasetId, workspaceId) => {
    // 해당 url 삭제된
    // const url = `datasets/synchronization`;
    // const form = new FormData();
    // if (datasetId !== undefined) {
    //   form.append('dataset_id', datasetId);
    // }
    // if (workspaceId !== undefined) {
    //   form.append('workspace_id', workspaceId);
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
  };

  /**
   * API 호출 GET
   * Dataset 정보 동기화
   * @param {number} datasetId 데이터셋 아이디
   * @param {number} workspaceId 워크스페이스 아이디
   */
  const syncData = async (datasetId) => {
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
  };

  const onSynchronization = async (datasetId, workspaceId) => {
    if (!loading[datasetId]) {
      // dataset sync 로딩 시작 dispatch
      dispatch(openMultiLoading(datasetId));
    }
    const isSyncRequest = await syncData(datasetId);
    if (isSyncRequest === false) {
      dispatch(closeMultiLoading(datasetId));
      return;
    }

    const isCheckSyncSuccess = await checkSyncThread(datasetId, workspaceId);
    // dataset sync 로딩 종료 dispatch
    if (isCheckSyncSuccess === true) {
      getDatasetsData();
    }
    dispatch(closeMultiLoading(datasetId));
  };

  /**
   * 데이터셋 전체 동기화
   */
  // const onAllSync = async () => {
  //   const allLoading = loading['all'];

  //   if (allLoading === false) {
  //     dispatch(openMultiLoading('all'));
  //     const url = `datasets/synchronization`;
  //     const response = await callApi({
  //       url,
  //       method: 'POST',
  //     });
  //     const { message, status, error } = response;
  //     if (status === STATUS_SUCCESS) {
  //       const result = await checkSyncThread();
  //       if (result === true) {
  //         getDatasetsData();
  //       }
  //     } else {
  //       errorToastMessage(error, message);
  //     }
  //     dispatch(closeMultiLoading('all'));
  //   }
  // };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */

  const selectInputHandler = (name, value) => {
    if (name === 'accessType') {
      setAccessType(value);
    } else {
      setSearchKey(value);
    }
  };

  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = (value) => {
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
   * 데이터셋 폴더 클릭시 파일 목록으로 이동
   * 어드민 페이지에서 상세 데이터셋을 못보게함
   *
   * @param {object} data 선택된 데이터셋 정보
   */
  const onRowClick = (data) => {
    // const {
    //   id: datasetId,
    //   workspace_id: workspaceId,
    //   dataset_name: name,
    //   description,
    //   access,
    //   permission_level,
    // } = data;
    // history.push({
    //   pathname: `/admin/datasets/${datasetId}/files`,
    //   state: {
    //     id: datasetId,
    //     name,
    //     description,
    //     accessType: access,
    //     permissionLevel: permission_level,
    //     workspaceId,
    //     loc: ['Home', name, 'Files'],
    //   },
    // });
  };

  useEffect(() => {
    loadModalComponent('CREATE_BUILTIN_MODEL');
  }, []);

  useEffect(() => {
    onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessType, searchKey]);

  useEffect(() => {
    getDatasetsData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AdminDatasetContent
      onCreate={onCreate}
      columns={columns}
      tableData={tableData}
      tableLoading={tableLoading}
      keyword={keyword}
      searchKey={searchKey}
      onSearch={onSearch}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      accessType={accessType}
      onAccessTypeChange={(value) => {
        selectInputHandler('accessType', value);
      }}
      totalRows={totalRows}
      toggledClearRows={toggledClearRows}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      deleteBtnDisabled={selectedRows.length === 0}
      onSelect={onSelect}
      onRowClick={onRowClick}
      // onAllSync={onAllSync}
      loading={loading['all']}
      onClear={onClear}
      onSortHandler={onSortHandler}
      handleRefresh={getDatasetsData}
    />
  );
}

export default AdminDatasetPage;
