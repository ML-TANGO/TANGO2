import { Button, ButtonV2, StatusCard } from '@tango/ui-react';

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
import { useHistory, useParams } from 'react-router-dom';
import { toast } from 'react-toastify';

// import DockerImageDeleteModal from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModal';
import DockerImageFormModalContent from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalContent';
import DockerImageFormModalFooter from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalFooter';
// Modal ContentsComponent
import DockerImageFormModalHeader from '@src/components/Modal/DockerImageFormModal/DockerImageFormModalHeader';
import DokcerImageLogModalContent from '@src/components/Modal/DockerImageLogModal/DockerImageLogModalContent.jsx';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
// Components
import AdminDockerImageContent from '@src/components/pageContents/admin/AdminDockerImageContent';
// CSS module
import style from '@src/components/pageContents/admin/AdminDockerImageContent/AdminDockerImageContent.module.scss';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
import {
  handleClosePopup,
  handleOpenPopup,
} from '@src/store/modules/popupState';

// Hooks

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import {
  convertBinaryByte,
  defaultSuccessToastMessage,
  errorToastMessage,
} from '@src/utils';

import classNames from 'classnames/bind';

const cx = classNames.bind(style);

export const calStatusCardRender = (status, t) => {
  switch (status) {
    case 0:
      return (
        <StatusCard
          text={t('pending')}
          status='pending'
          size='medium'
          // leftIcon={ProgressYellow}
          customStyle={{
            width: 'auto',
            fontSize: '12px',
            height: '28px',
          }}
          // leftIconStyle={{
          //   marginRight: '5px',
          // }}
          isProgressStatus={true}
        />
      );
    case 1:
      return (
        <StatusCard
          text={t('install')}
          status='blue'
          size='medium'
          // leftIcon={ProgressGreen}
          customStyle={{
            width: 'auto',
            fontSize: '12px',
            height: '28px',
          }}
          // leftIconStyle={{
          //   marginRight: '5px',
          // }}
          isProgressStatus={true}
        />
      );
    case 2:
      return (
        <StatusCard
          text={t('complete')}
          status='gray'
          size='medium'
          // leftIcon={Ready}
          customStyle={{
            width: 'auto',
            fontSize: '12px',
            height: '28px',
          }}
          // leftIconStyle={{
          //   marginRight: '5px',
          // }}
          isProgressStatus={false}
        />
      );
    case 3:
      return (
        <StatusCard
          text={t('fail')}
          status='failed'
          size='medium'
          // leftIcon={Failed}
          customStyle={{
            width: 'auto',
            fontSize: '12px',
            height: '28px',
          }}
          // leftIconStyle={{
          //   marginRight: '5px',
          // }}
          isProgressStatus={false}
        />
      );
    case 4:
      return (
        <StatusCard
          text={t('delete.label')}
          status='stop'
          size='medium'
          // leftIcon={ProgressGray}
          customStyle={{
            width: 'auto',
            fontSize: '12px',
            height: '28px',
          }}
          // leftIconStyle={{
          //   marginRight: '5px',
          // }}
          isProgressStatus={true}
        />
      );
    default:
      return <></>;
  }
};

function AdminDockerImagePage() {
  // Router Hooks
  const history = useHistory();

  // Redux Hooks
  const dispatch = useDispatch();

  const { t } = useTranslation();
  const { id } = useParams();

  const [workspaceId, setWorkspaceId] = useState(id);
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
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
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(4);

  const columns = [
    {
      name: t('status.label'),
      selector: (row) => row.status,
      sortable: false,
      minWidth: '90px',
      maxWidth: '110px',
      cell: ({ status }) => {
        const ComStatusCard = calStatusCardRender(status, t);
        return ComStatusCard;
      },
    },
    {
      name: '로그',
      selector: (row) => row.status,
      sortable: false,
      minWidth: '90px',
      maxWidth: '100px',
      cell: ({ id, status, image_name, type }) => {
        switch (status) {
          case 1:
          case 2:
          case 3:
            return (
              <>
                {type !== 0 && (
                  <ButtonV2
                    label={t('log.label')}
                    onClick={() => showLog(id, image_name)}
                    type='clear'
                    size='l'
                    // colorType='gray'
                    iconPosition='right'
                    style={{ padding: '0px' }}
                    // 아이콘 추가
                  />
                )}
              </>
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
      selector: (row) => row.type,
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
            return '-';
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
      selector: (row) => row.access,
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
      selector: (row) => row.image_name,
      sortable: false,
      minWidth: '180px',
      wrap: true,
      format: ({ image_name, workspace, access }) => (
        <div className={cx('name-box')}>
          <span className={cx('name')}>
            {image_name && image_name.length ? image_name : '-'}
          </span>
          {access === 0 ? (
            workspace.length > 0 ? (
              <div className={cx('workspace')}>
                {workspace.map((ws, idx) => (
                  <span key={idx}>
                    {ws.workspace_name}
                    {idx !== workspace.length - 1 && ', '}
                  </span>
                ))}
              </div>
            ) : (
              <div className={cx('workspace')}>-</div>
            )
          ) : (
            <div className={cx('workspace')}>All Workspaces</div>
          )}
        </div>
      ),
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
      selector: (row) => row.size,
      sortable: true,
      maxWidth: '132px',
      cell: ({ size, workspace, access }) => {
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
    // {
    //   name: t('workspace.label'),
    //   selector: 'workspace_name',
    //   sortable: false,
    //   minWidth: '180px',
    //   cell: ({ workspace, access }) => {
    //     return access === 0 ? (
    //       workspace.length > 0 ? (
    //         <div>
    //           {workspace.map((ws, idx) => (
    //             <span key={idx}>
    //               {ws.workspace_name}
    //               {idx !== workspace.length - 1 && ', '}
    //             </span>
    //           ))}
    //         </div>
    //       ) : (
    //         '-'
    //       )
    //     ) : (
    //       'All Workspaces'
    //     );
    //   },
    // },
    {
      name: t('creator.label'),
      selector: (row) => row.user_name,
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
      selector: (row) => row.create_datetime,
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
            opacity: row.status === 2 && row.type !== 0 ? 1 : 0.2,
          }}
          className='table-icon'
          src='/images/icon/00-ic-basic-pen.svg'
          alt='edit'
          onClick={() => {
            if (row.status === 2 && row.type !== 0) onUpdate(row);
          }}
        />
      ),
      button: true,
    },
  ];

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  /**
   * 도커이미지 생성
   */
  const onCreate = () => {
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
        },
      }),
    );
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
  };

  /**
   * 도커이미지 수정
   *
   * @param {Objeect} row 도커이미지 데이터
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
        },
      }),
    );
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
            isAnimation: true,
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
      setToggledClearRows(!toggledClearRows);
      getImages();
      defaultSuccessToastMessage('delete');
      dispatch(closeModal('DELETE_DOCKER_IMAGE'));
      setSelectedRows([]);
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
            func: () => {
              this.dispatch(closeModal('DELETE_DOCKER_IMAGE'));
            },
          },
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
   * 검색
   *
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
      if (searchKey.value === 'workspace_name') {
        tableData = tableData.filter((item) => {
          let found = false;
          if (item.access === 1) {
            found = true;
            return found;
          }
          for (let i = 0; i < item.workspace.length; i += 1) {
            if (item.workspace[i].workspace_name.includes(value)) {
              found = true;
              break;
            }
          }
          return found;
        });
      } else {
        tableData = tableData.filter((item) =>
          item[searchKey.value].includes(value),
        );
      }
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
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
    history.push({ state: undefined });
  };

  /**
   * API 호출 GET
   * 어드민 도커이미지 데이터 가져오기
   */
  const getImages = useCallback(async () => {
    const response = await callApi({
      url: 'images',
      method: 'get',
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      result?.list?.forEach((list) => {
        if (list.workspace.length > 0 && list.workspace[0].workspace_id) {
          setWorkspaceId(list.workspace[0].workspace_id);
        }
      });
      setOriginData(result.list);
      setLoading(false);
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
            value: 'user_name',
          });
        }
      }
      return true;
    } else {
      errorToastMessage(error, message);
      return false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history.location.state, keyword, t]);

  useEffect(() => {
    loadModalComponent('CREATE_DOCKER_IMAGE');
    loadModalComponent('LOG_DOCKER_IMAGE');
    loadModalComponent('DELETE_DOCKER_IMAGE');
    getImages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (originData.length !== 0) onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadType, releaseType, searchKey, originData, keyword]);

  // useIntervalCall(getImages, 1000);

  return (
    <AdminDockerImageContent
      toggledClearRows={toggledClearRows}
      columns={columns}
      tableData={tableData}
      keyword={keyword}
      searchKey={searchKey}
      onClear={onClear}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      onSearch={onSearch}
      uploadType={uploadType}
      onUploadTypeChange={(value) => {
        selectInputHandler('uploadType', value);
      }}
      releaseType={releaseType}
      onReleaseTypeChange={(value) => {
        selectInputHandler('releaseType', value);
      }}
      onCreate={onCreate}
      onSelect={onSelect}
      loading={loading}
      totalRows={totalRows}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      deleteBtnDisabled={selectedRows.length === 0}
      onSortHandler={onSortHandler}
      getImages={getImages}
    />
  );
}

export default AdminDockerImagePage;
