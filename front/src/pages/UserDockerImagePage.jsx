// Components
import { Button, StatusCard } from '@jonathan/ui-react';

import { convertLocalTime } from '@src/datetimeUtils';
import { loadModalComponent } from '@src/modal';
import Failed from '@src/static/images/icon/ic-status-failed.svg';
import ProgressGray from '@src/static/images/icon/ic-status-progress-gray.svg';
import ProgressGreen from '@src/static/images/icon/ic-status-progress-green.svg';
import ProgressYellow from '@src/static/images/icon/ic-status-progress-yellow.svg';
// Icon
import Ready from '@src/static/images/icon/ic-status-ready.svg';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useParams } from 'react-router-dom';
import { toast } from 'react-toastify';

import DockerImageFormModalContent from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalContent';
import DockerImageFormModalFooter from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalFooter';
// Modal ContentsComponent
import DockerImageFormModalHeader from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalHeader';
import DokcerImageLogModalContent from '@src/components/Modal/DockerImageLogModal/DockerImageLogModalContent.jsx';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import UserDockerImageContent from '@src/components/pageContents/user/UserDockerImageContent';

import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
import {
  handleClosePopup,
  handleOpenPopup,
} from '@src/store/modules/popupState';
// Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import {
  convertBinaryByte,
  defaultSuccessToastMessage,
  errorToastMessage,
} from '@src/utils';

import { calStatusCardRender } from './AdminDockerImagePage';

function UserDockerImagePage({ trackingEvent }) {
  const { t } = useTranslation();
  const { id } = useParams();
  const { id: workspaceId } = useParams();

  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(4);

  const [uploadType, setUploadType] = useState({
    label: 'allCreateType.label',
    value: 'all',
  });
  const [releaseType, setReleaseType] = useState({
    label: 'allReleaseType.label',
    value: 'all',
  });
  const [keyword, setKeyword] = useState('');
  const [searchKey, setSearchKey] = useState({
    label: 'dockerImageName.label',
    value: 'image_name',
  });

  const dispatch = useDispatch();

  const columns = [
    {
      name: t('status.label'),
      selector: 'status',
      sortable: false,
      minWidth: '168px',
      maxWidth: '200px',
      cell: ({ id, status, image_name, type }) => {
        switch (status) {
          case 0:
            return (
              <StatusCard
                text={t('pending')}
                status='pending'
                size='medium'
                leftIcon={ProgressYellow}
                customStyle={{
                  width: 'auto',
                  fontSize: '12px',
                }}
                leftIconStyle={{
                  marginRight: '5px',
                }}
                isProgressStatus={true}
              />
            );
          case 1:
            return (
              <>
                <StatusCard
                  text={t('install')}
                  status='green'
                  size='medium'
                  leftIcon={ProgressGreen}
                  customStyle={{
                    width: 'auto',
                    marginRight: '10px',
                    fontSize: '12px',
                  }}
                  leftIconStyle={{
                    marginRight: '5px',
                  }}
                  isProgressStatus={true}
                />
                {type !== 0 && (
                  <Button
                    type='primary-reverse'
                    size='small'
                    customStyle={{
                      padding: '0px 12px',
                      border: '0',
                    }}
                    onClick={() => showLog(id, image_name)}
                  >
                    {t('log.label')}
                  </Button>
                )}
              </>
            );
          case 2:
            return (
              <>
                <StatusCard
                  text={t('complete')}
                  status='blue'
                  size='medium'
                  leftIcon={Ready}
                  customStyle={{
                    width: 'auto',
                    marginRight: '10px',
                    fontSize: '12px',
                  }}
                  leftIconStyle={{
                    marginRight: '5px',
                  }}
                  isProgressStatus={false}
                />
                {type !== 0 && (
                  <Button
                    type='primary-reverse'
                    size='small'
                    customStyle={{
                      padding: '0px 12px',
                      border: '0',
                    }}
                    onClick={() => showLog(id, image_name)}
                  >
                    {t('log.label')}
                  </Button>
                )}
              </>
            );
          case 3:
            return (
              <>
                <StatusCard
                  text={t('fail')}
                  status='failed'
                  size='medium'
                  leftIcon={Failed}
                  customStyle={{
                    width: 'auto',
                    marginRight: '10px',
                    fontSize: '12px',
                  }}
                  leftIconStyle={{
                    marginRight: '5px',
                  }}
                  isProgressStatus={false}
                />
                {type !== 0 && (
                  <Button
                    type='primary-reverse'
                    size='small'
                    customStyle={{
                      padding: '0px 12px',
                      border: '0',
                    }}
                    onClick={() => showLog(id, image_name)}
                  >
                    {t('log.label')}
                  </Button>
                )}
              </>
            );
          case 4:
            return (
              <StatusCard
                text={t('deleting')}
                status='stop'
                size='medium'
                leftIcon={ProgressGray}
                customStyle={{
                  width: 'auto',
                  marginRight: '10px',
                  fontSize: '12px',
                }}
                leftIconStyle={{
                  marginRight: '5px',
                }}
                isProgressStatus={true}
              />
            );
          default:
            return <></>;
        }
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('createType.label')}
          idx={0}
        />
      ),
      selector: 'type',
      sortable: true,
      maxWidth: '150px',
      cell: ({ type }) => {
        switch (type) {
          case 0:
            return 'Built-in';
          case 1:
            return 'Pull';
          case 2:
            return 'Tar';
          case 3:
            return 'Dockerfile Build';
          case 4:
            return 'Tag';
          case 5:
            return 'NGC';
          case 6:
            return 'Commit';
          default:
            return `${t('clone.label')}`;
        }
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('releaseType.label')}
          idx={1}
        />
      ),
      selector: 'access',
      sortable: true,
      maxWidth: '132px',
      cell: ({ access }) => {
        if (access === 0) {
          return t('workspace.label');
        }
        return t('global.label');
      },
    },
    {
      name: t('dockerImageName.label'),
      selector: 'image_name',
      sortable: false,
      minWidth: '180px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('size.label')}
          idx={2}
        />
      ),
      selector: 'size',
      sortable: true,
      maxWidth: '132px',
      cell: ({ size }) => {
        return (
          <>
            {size !== null
              ? Number.isNaN(Number(size))
                ? size
                : convertBinaryByte(size)
              : '-'}
          </>
        );
      },
    },
    {
      name: t('creator.label'),
      selector: 'user_name',
      sortable: false,
      maxWidth: '170px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('createdAt.label')}
          idx={3}
        />
      ),
      selector: 'create_datetime',
      sortable: true,
      maxWidth: '192px',
      cell: ({ create_datetime: date }) => convertLocalTime(date),
    },
    {
      name: t('clone.label'),
      maxWidth: '64px',
      cell: (row) => (
        <img
          style={{
            width: '30px',
            opacity: row.status === 2 && row.type !== 0 ? 1 : 0.2,
          }}
          className='table-icon'
          src='/images/icon/00-ic-basic-copy-o.svg'
          alt='clone'
          onClick={() => {
            if (row.status === 2 && row.type !== 0) onDuplicate(row);
          }}
        />
      ),
      button: true,
    },
    {
      name: t('edit.label'),
      maxWidth: '64px',
      cell: (row) => (
        <img
          style={{
            opacity:
              row.status === 2 &&
              (row.has_permission === 1 || row.has_permission === 2)
                ? 1
                : 0.2,
          }}
          className='table-icon'
          src='/images/icon/00-ic-basic-pen.svg'
          alt='edit'
          onClick={() => {
            if (
              row.status === 2 &&
              (row.has_permission === 1 || row.has_permission === 2)
            ) {
              onUpdate(row);
            }
          }}
        />
      ),
      button: true,
    },
  ];

  /**
   * 검색 필터링
   * @param {string} value 검색할 내용
   */
  const onSearch = (value) => {
    let tableData = originData;

    if (uploadType.value !== 'all') {
      tableData = tableData.filter(
        (item) => item.type === Number(uploadType.value),
      );
    }

    if (releaseType.value !== 'all') {
      tableData = tableData.filter(
        (item) => item.access === Number(releaseType.value),
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
   * 도커이미지 설치 로그 모달
   * @param {number} id 도커이미지 아이디
   * @param {string} name 도커이미지 이름
   */
  const showLog = async (id, name) => {
    const { status, result, error, message } = await callApi({
      url: `images/install-log?image_id=${id}`,
      method: 'get',
    });

    if (status === STATUS_SUCCESS) {
      if (result) {
        const { log, status } = result;

        dispatch(
          handleOpenPopup({
            type: 'sub',
            frontTitle: calStatusCardRender(status, t),
            popupTitle: name,
            popupContents: <DokcerImageLogModalContent log={log} />,
            submitBtnLabel: t('confirm.label'),
            handleSubmit: () => {
              dispatch(handleClosePopup());
            },
            style: {
              width: '686px',
            },
          }),
        );
        return;
      }

      toast.info(t('image.log.empty.message'));
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * API 호출 GET
   * 사용자 도커이미지 데이터 가져오기
   */
  const getImages = useCallback(async () => {
    const response = await callApi({
      url: `images?workspace_id=${id}`,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setOriginData(result.list);
      return true;
    } else {
      errorToastMessage(error, message);
      return false;
    }
  }, [id]);

  /**
   * 도커이미지 생성
   */
  const onCreate = async () => {
    // const check = await checkCreationLimit();
    // if (!check) return;
    dispatch(
      openModal({
        modalType: 'CREATE_DOCKER_IMAGE',
        modalData: {
          headerRender: DockerImageFormModalHeader,
          contentRender: DockerImageFormModalContent,
          footerRender: DockerImageFormModalFooter,
          submit: {
            text: 'create.label',
            func: () => {
              getImages();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceId,
        },
      }),
    );
    trackingEvent({
      category: 'User Docker Image Page',
      action: 'Open Upload Docker Image Modal',
    });
  };

  /**
   * 도커이미지 복제
   *
   * @param {object} row 도커이미지 데이터
   */
  const onDuplicate = (row) => {
    dispatch(
      openModal({
        modalType: 'DUPLICATE_DOCKER_IMAGE',
        modalData: {
          headerRender: DockerImageFormModalHeader,
          contentRender: DockerImageFormModalContent,
          footerRender: DockerImageFormModalFooter,
          submit: {
            text: 'clone.label',
            func: () => {
              getImages();
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
      category: 'User Docker Image Page',
      action: 'Open Duplicate Docker Image Modal',
    });
  };

  /**
   * 도커이미지 수정
   *
   * @param {object} row 도커이미지 데이터
   */
  const onUpdate = (row) => {
    dispatch(
      openModal({
        modalType: 'EDIT_DOCKER_IMAGE',
        modalData: {
          headerRender: DockerImageFormModalHeader,
          contentRender: DockerImageFormModalContent,
          footerRender: DockerImageFormModalFooter,
          submit: {
            text: 'edit.label',
            func: () => {
              getImages();
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
      category: 'User Docker Image Page',
      action: 'Open Edit Docker Image Modal',
    });
  };

  /**
   * API 호출 Delete
   * 도커이미지 삭제
   * 체크박스 선택된 데이터 삭제
   */
  const onDelete = async (deleteList) => {
    const { thisList, allList } = deleteList;
    const wsListItem = [];
    thisList?.forEach((id) => wsListItem.push(id.value));
    const allListItem = [];
    allList?.forEach((id) => allListItem.push(id.value));

    const body = {
      workspace_id: workspaceId,
      delete_all_list: allListItem,
      delete_ws_list: wsListItem,
    };

    const response = await callApi({
      url: 'images',
      method: 'delete',
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows((toggledClearRows) => !toggledClearRows);
      getImages();
      defaultSuccessToastMessage('delete');
      dispatch(closeModal('DELETE_DOCKER_IMAGE'));
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 도커이미지 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      openModal({
        modalType: 'DELETE_DOCKER_IMAGE',
        modalData: {
          submit: {
            text: 'delete.label',
            func: (list) => {
              onDelete(list);
            },
          },
          data: {
            selectedRows,
          },
          cancel: {
            text: 'cancel.label',
          },
        },
      }),
    );
  };

  /**
   * 도커이미지 생성 제한 팝업
   * @param {number} total 무료 생성 가능 개수
   */
  const openLimitCreationPopup = (total) => {
    dispatch(
      openConfirm({
        title: 'dockerImageCreationCautionPopup.title.label',
        content: t('dockerImageCreationCautionPopup.message').replace(
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
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = (name, value) => {
    if (name === 'releaseType') {
      setReleaseType(value);
    } else if (name === 'uploadType') {
      setUploadType(value);
    } else if (name === 'searchKey') {
      setSearchKey(value);
    }
  };

  /**
   * Action 브래드크럼
   */
  const breadCrumbHandler = useCallback(() => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Docker Image',
            t,
          },
        },
      ]),
    );
  }, [dispatch, t]);

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

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  useEffect(() => {
    loadModalComponent('LOG_DOCKER_IMAGE');
    loadModalComponent('CREATE_DOCKER_IMAGE');
    loadModalComponent('DELETE_DOCKER_IMAGE');
  }, []);

  useEffect(() => {
    if (originData.length !== 0) onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadType, releaseType, searchKey, originData, keyword]);

  useEffect(() => {
    breadCrumbHandler();
  }, [breadCrumbHandler]);

  useIntervalCall(getImages, 1000);

  return (
    <UserDockerImageContent
      toggledClearRows={toggledClearRows}
      onSelect={onSelect}
      onCreate={onCreate}
      columns={columns}
      tableData={tableData}
      keyword={keyword}
      searchKey={searchKey}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      onSearch={onSearch}
      onClear={onClear}
      uploadType={uploadType}
      onUploadTypeChange={(value) => {
        selectInputHandler('uploadType', value);
      }}
      releaseType={releaseType}
      onReleaseTypeChange={(value) => {
        selectInputHandler('releaseType', value);
      }}
      loading={loading}
      totalRows={totalRows}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      deleteBtnDisabled={selectedRows.length === 0}
      onSortHandler={onSortHandler}
    />
  );
}

export default UserDockerImagePage;
