import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory } from 'react-router-dom';

import { Badge, Button } from '@jonathan/ui-react';

// Utils
import { convertLocalTime } from '@src/datetimeUtils';

import Status from '@src/components/atoms/Status';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
// Components
import AdminWorkspaceContent from '@src/components/pageContents/admin/AdminWorkspaceContent';
// CSS module
import style from '@src/components/pageContents/admin/AdminWorkspaceContent/AdminWorkspaceContent.module.scss';

// Actions
import { openModal } from '@src/store/modules/modal';
import { handleOpenPopup } from '@src/store/modules/popupState';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';

const cx = classNames.bind(style);

function AdminWorkspacePage() {
  const history = useHistory();
  const dispatch = useDispatch();
  const { t } = useTranslation();
  const { workspace } = useSelector((state) => state.alarmNotice, shallowEqual);

  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [workspaceStatus, setWorkspaceStatus] = useState({
    label: t('allStatus.label'),
    value: 'all',
  });
  const [searchKey, setSearchKey] = useState({
    label: t('workspaceName.label'),
    value: 'name',
  });
  const [keyword, setKeyword] = useState('');
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(4);

  /**
   * 테이블 데이터 컬럼 정의
   */
  const columns = [
    {
      name: t('status.label'),
      selector: 'status',
      sortable: false,
      maxWidth: '128px',
      cell: ({ status }) => (
        <Badge
          type={status}
          label={t(status)}
          size='xl'
          // customStyle={{}}
        />
      ),
    },
    {
      name: t('workspaceName.label'),
      selector: 'name',
      sortable: false,
      grow: 1,
      minWidth: '350px',
      cell: (row) => {
        return (
          <div className={cx('name-box')}>
            <div className={cx('name')}>{row?.name}</div>

            {/* <div className={cx('img-box')}> */}
            <img
              className={cx('img')}
              src='/images/icon/00-ic-basic-pen.svg'
              alt='edit'
              style={{
                opacity: !row.isCheckDisabled ? 1 : 0.2,
              }}
              onClick={() => {
                if (row.isCheckDisabled) return;
                onUpdate(row);
              }}
            />
            {/* </div> */}
          </div>
        );
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('startDate.label')}
          idx={0}
        />
      ),
      selector: 'start_datetime',
      sortable: true,
      maxWidth: '213px',
      cell: ({ start_datetime: date }) =>
        convertLocalTime(date, 'YYYY-MM-DD HH:mm'),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('endDate.label')}
          idx={1}
        />
      ),
      selector: 'end_datetime',
      sortable: true,
      maxWidth: '213px',
      cell: ({ end_datetime: date }) =>
        convertLocalTime(date, 'YYYY-MM-DD HH:mm'),
    },

    {
      name: t('gpuInUse.label'),
      selector: 'gpu',
      sortable: false,
      maxWidth: '200px',

      cell: ({ gpu: { total } }) => {
        return total?.used ?? 0;
      },
    },
    {
      name: t('manager.label'),
      selector: 'manager',
      sortable: false,
      maxWidth: '180px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('user.label')}
          idx={2}
        />
      ),
      selector: 'user.total',
      sortable: true,
      maxWidth: '144px',
      cell: ({ user: { total } }) => total,
    },
    {
      name: (
        <div style={{}} className='center'>
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('createdAt.label')}
            idx={3}
          />
        </div>
      ),
      selector: 'create_datetime',
      sortable: true,
      cell: ({ create_datetime: date, id, type }) => {
        if (!date)
          return (
            <Button onClick={() => onConfirm(id)}>
              {t(
                type === 'update' ? 'update.request.btn' : 'create.request.btn',
              )}
            </Button>
          );
        return convertLocalTime(date);
      },
    },
    // {
    //   name: t('edit.label'),
    //   maxWidth: '64px',
    //   cell: (row) => (
    //     <img
    //       className='table-icon'
    //       src='/images/icon/00-ic-basic-pen.svg'
    //       alt='edit'
    //       style={{
    //         opacity: !row.isCheckDisabled ? 1 : 0.2,
    //       }}
    //       onClick={() => {
    //         if (row.isCheckDisabled) return;
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
   * 어드민 워크스페이스 데이터 가져오기
   */
  const getWorkspacesData = async () => {
    setLoading(true);
    const response = await callApi({
      url: 'workspaces',
      method: 'GET',
    });
    const { status, result, message, error } = response;
    const { request_workspace_list } = result;
    const shallowCopyRequestList = request_workspace_list.slice();
    const filterRequestList = shallowCopyRequestList.map((el) => {
      return {
        isCheckDisabled: true,
        status: 'pending',
        name: el.name,
        start_datetime: el.start_datetime,
        end_datetime: el.end_datetime,
        gpu: {},
        manager: el.manager_name,
        user: {
          total: el.user_list.length,
        },
        create_datetime: 0,
        id: `${el.id}t`,
        type: el.type,
      };
    });

    const combineArray = [...filterRequestList, ...result.list];

    if (status === STATUS_SUCCESS) {
      setOriginData(combineArray);
      setTableData(combineArray);
      setTotalRows(combineArray.length);
      setSelectedRows([]);
      setLoading(false);
      // 상세정보에서 넘어 올 경우
      if (history.location.state) {
        const { user } = history.location.state;
        if (user) {
          setKeyword(user);

          selectInputHandler('searchKey', {
            label: t('user.label'),
            value: 'user',
          });
        }
      }

      if (keyword !== '') onSearch(keyword);
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 워크스페이스 생성
   */
  const onCreate = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_WORKSPACE',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {
              getWorkspacesData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceListData: originData,
          isAdmin: true,
        },
      }),
    );
  };

  /**
   * 워크스페이스 수정
   *
   * @param {object} row 워크스페이스 데이터
   */
  const onUpdate = (row) => {
    dispatch(
      openModal({
        modalType: 'EDIT_WORKSPACE',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              getWorkspacesData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: row,
          workspaceListData: originData,
          isAdmin: true,
        },
      }),
    );
  };

  /**
   * 워크스페이스 확인
   *
   * @param {object} id 워크스페이스 id
   */
  const onConfirm = (id) => {
    dispatch(
      openModal({
        modalType: 'WORKSPACE_CONFIRM_MODAL',
        modalData: {
          workspaceId: +id.replace('t', ''),
          getWorkSpaceFunc: () => {
            getWorkspacesData();
          },
        },
      }),
    );
  };

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
  };

  /**
   * API 호출 Delete
   * 워크스페이스 삭제
   * 체크박스 선택된 워크스페이스 삭제
   */
  const onDelete = async () => {
    const ids = selectedRows.map(({ id }) => id);
    const response = await callApi({
      url: `workspaces/${ids.join(',')}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows(!toggledClearRows);
      getWorkspacesData();
      defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 워크스페이스 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: t('deleteWorkspacePopup.title.label'),
        popupContents: t('deleteWorkspacePopup.message'),
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('delete.label'),
        handleSubmit: async () => {
          await onDelete();
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
    if (name === 'searchKey') {
      setSearchKey(value);
    } else if (name === 'workspaceStatus') {
      setWorkspaceStatus(value);
    }
  };

  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = (value) => {
    let tableData = originData;

    if (workspaceStatus.value !== 'all') {
      tableData = tableData.filter(
        (item) => item.status === workspaceStatus.value,
      );
    }
    if (value !== '') {
      if (searchKey.value === 'user') {
        tableData = tableData.filter((item) => {
          let found = false;
          for (let i = 0; i < item.user.list.length; i += 1) {
            if (item.user.list[i].name.includes(value)) {
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
   * 테이블 데이터 상세정보에서 더보기 항목 이동
   *
   * @param {string} workspace 워크스페이스 이름
   * @param {string} type 이동할 페이지 (trainings | deployments | docker_images | datasets)
   */
  const moreList = (workspace, type) => {
    history.push({
      pathname: `${type}`,
      state: {
        workspace,
      },
    });
  };

  useEffect(() => {
    loadModalComponent('CREATE_WORKSPACE');
    loadModalComponent('WORKSPACE_CONFIRM_MODAL');
  }, []);

  useEffect(() => {
    if (originData.length !== 0) onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceStatus, searchKey, originData, keyword]);

  useEffect(() => {
    getWorkspacesData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  return (
    <AdminWorkspaceContent
      onCreate={onCreate}
      onSelect={onSelect}
      columns={columns}
      tableData={tableData}
      keyword={keyword}
      searchKey={searchKey}
      onSearch={onSearch}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      workspaceStatus={workspaceStatus}
      onStatusChange={(value) => {
        selectInputHandler('workspaceStatus', value);
      }}
      loading={loading}
      totalRows={totalRows}
      toggledClearRows={toggledClearRows}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      deleteBtnDisabled={selectedRows.length === 0}
      moreList={moreList}
      onClear={onClear}
      onSortHandler={onSortHandler}
      handleRefresh={getWorkspacesData}
    />
  );
}

export default AdminWorkspacePage;
