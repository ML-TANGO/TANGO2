import { StatusCard } from '@jonathan/ui-react';

import { loadModalComponent } from '@src/modal';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
// Components
import AdminNetworkContent from '@src/components/pageContents/admin/AdminNetworkContent';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function AdminNetworkPage({ trackingEvent }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  // State
  const [groupViewData, setGroupViewData] = useState(null);
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [searchKey, setSearchKey] = useState({
    label: 'groupName.label',
    value: 'name',
  });
  const [statusFilter, setStatusFilter] = useState({
    label: 'allStatus.label',
    value: 'all',
  });
  const [categoryFilter, setCategoryFilter] = useState({
    label: 'allCategory.label',
    value: 'all',
  });

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(3);

  const columns = [
    {
      name: t('status.label'),
      selector: 'status',
      sortable: false,
      maxWidth: '128px',
      cell: (row) => (
        <StatusCard
          status={row.is_available ? 'ready' : 'error'}
          text={
            row.is_available ? t('available.label') : t('unavailable.label')
          }
          type='default'
        />
      ),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('network.groupName.label')}
          idx={0}
        />
      ),
      selector: 'name',
      sortable: true,
      minWidth: '110px',
      maxWidth: '200px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('network.category.label')}
          idx={1}
        />
      ),
      selector: 'category',
      sortable: true,
      maxWidth: '180px',
      cell: (row) =>
        row.category === 0 ? t('ethernet.label') : t('infiniBand.label'),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('network.speed.label')}
          idx={2}
        />
      ),
      selector: 'speed',
      sortable: true,
      maxWidth: '160px',
      cell: (row) => `${row.speed} Gbps`,
    },
    {
      name: t('ip.label'),
      selector: 'cni_info',
      sortable: false,
      minWidth: '130px',
      maxWidth: '260px',
      cell: (row) => {
        const ip = row?.cni_info?.ip;
        const subnetMask = row?.cni_info?.subnet_mask;
        if (ip) {
          return `${ip}/${subnetMask}`;
        } else {
          return '-';
        }
      },
    },
    {
      name: t('description.label'),
      selector: 'description',
      sortable: false,
      minWidth: '130px',
    },
    {
      name: t('edit.label'),
      minWidth: '64px',
      maxWidth: '64px',
      cell: (row) => (
        <img
          src='/images/icon/00-ic-basic-pen.svg'
          alt='edit'
          className='table-icon'
          onClick={() => {
            openGroupSettingModal(row);
          }}
        />
      ),
      button: true,
    },
  ];

  /**
   * 테이블 정보 - 노드 정보, 네트워크 그룹 이름, 스토리지 정보
   */
  const getNetworkGroupInfo = useCallback(async () => {
    const response = await callApi({
      url: 'networks/network-group',
      method: 'GET',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setOriginData(result);
      setTableData(result);
      setTotalRows(result.length);
    } else {
      errorToastMessage(error, message);
    }
    return response;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * 네트워크 시각화 데이터
   */
  const getNetworkGroupView = useCallback(async () => {
    const response = await callApi({
      url: 'networks/network-group-view',
      method: 'GET',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const ethernetView = result?.ethernet_network_group_view;
      const infinibandView = result?.infiniband_network_group_view;
      setGroupViewData({ ethernet: ethernetView, infiniband: infinibandView });
    } else {
      errorToastMessage(error, message);
    }
    return response;
  }, []);

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const onCreate = async () => {
    dispatch(
      openModal({
        modalType: 'CREATE_NETWORK_GROUP',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {
              dispatch(closeModal('CREATE_NETWORK_GROUP'));
              getNetworkGroupInfo();
              getNetworkGroupView();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
        },
      }),
    );
  };

  const onDelete = async () => {
    const ids = selectedRows.map(({ id }) => id);
    const response = await callApi({
      url: 'networks/network-group',
      method: 'delete',
      body: { network_group_id_list: ids },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows(!toggledClearRows);
      getNetworkGroupInfo();
      getNetworkGroupView();
      defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 네트워크 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'network.delete.popup.title.label',
        content: 'network.delete.popup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
      }),
    );
  };

  const openGroupSettingModal = (row) => {
    dispatch(
      openModal({
        modalType: 'NETWORK_GROUP_SETTING',
        modalData: {
          submit: {
            text: 'update.label',
            func: () => {
              getNetworkGroupInfo();
              getNetworkGroupView();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: row,
        },
      }),
    );
    trackingEvent({
      category: 'Admin Network Page',
      action: 'Open Network Group Setting Modal',
    });
  };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = (name, value) => {
    if (name === 'status') {
      setStatusFilter(value);
    } else if (name === 'category') {
      setCategoryFilter(value);
    } else if (name === 'searchKey') {
      setSearchKey(value);
    }
  };

  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = useCallback(
    (value) => {
      let tableData = [...originData];

      if (statusFilter.value !== 'all') {
        tableData = tableData.filter(
          (item) => item.is_available === statusFilter.value,
        );
      }

      if (categoryFilter.value !== 'all') {
        tableData = tableData.filter(
          (item) => item.category === categoryFilter.value,
        );
      }

      if (searchKey.value === 'name') {
        tableData = tableData.filter((item) =>
          item?.name.toLowerCase().includes(value.toLowerCase()),
        );
      } else if (value !== '') {
        tableData = tableData.filter((item) =>
          item[searchKey.value].includes(value),
        );
      }

      setKeyword(value);
      setTableData(tableData);
      setTotalRows(tableData.length);
    },
    [categoryFilter.value, originData, searchKey.value, statusFilter.value],
  );

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
    onSearch('');
  };

  useEffect(() => {
    loadModalComponent('CREATE_NETWORK_GROUP');
  }, []);

  useEffect(() => {
    onSearch(keyword);
  }, [keyword, onSearch, searchKey, statusFilter]);

  useEffect(() => {
    getNetworkGroupInfo();
    getNetworkGroupView();
  }, [getNetworkGroupInfo, getNetworkGroupView]);

  return (
    <AdminNetworkContent
      groupViewData={groupViewData}
      tableData={tableData}
      columns={columns}
      totalRows={totalRows}
      onStatusFilterChange={(value) => {
        selectInputHandler('status', value);
      }}
      statusFilter={statusFilter}
      onCategoryFilterChange={(value) => {
        selectInputHandler('category', value);
      }}
      categoryFilter={categoryFilter}
      searchKey={searchKey}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      keyword={keyword}
      onSearch={onSearch}
      onSelect={onSelect}
      onClear={onClear}
      toggledClearRows={toggledClearRows}
      onCreate={onCreate}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      deleteBtnDisabled={selectedRows.length === 0}
      onSortHandler={onSortHandler}
    />
  );
}

export default AdminNetworkPage;
