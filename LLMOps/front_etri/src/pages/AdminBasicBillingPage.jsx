import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import AdminBasicBillingContent from '@src/components/pageContents/admin/AdminBasicBilling/AdminBasicBillingContent';

import { callApi, STATUS_SUCCESS } from '@src/network';

const AdminBasicBillingPage = () => {
  const { t } = useTranslation();

  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [basicInfo, setBasicInfo] = useState({
    activeWorkspace: 0,
    workspaceBasicFee: 0,
    member: 0,
    addMemberCost: 0,
    timeUnit: 'hour',
    outBoundNetwork: [],
  });
  const [searchKey, setSearchKey] = useState({
    label: '',
    value: '',
  });
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(5);

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('workspaceName.label')}
          idx={0}
        />
      ),
      sortable: true,
      selector: 'workspace_name',
      minWidth: '300px',
      maxWidth: '400px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('workspaceManager.label')}
          idx={1}
        />
      ),
      sortable: true,
      selector: 'workspace_manager',
      minWidth: '300px',
      maxWidth: '400px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('currentMemberCount')}
          idx={2}
        />
      ),
      sortable: true,
      selector: 'workspace_user_count',
      minWidth: '200px',
      maxWidth: '250px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('addMemberCount')}
          idx={3}
        />
      ),
      sortable: true,
      selector: 'add_user_count',
      minWidth: '200px',
      maxWidth: '250px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('totalUsageOutBound')}
          idx={4}
        />
      ),
      sortable: true,
      selector: 'out_bound_network_usage',
      minWidth: '200px',
      maxWidth: '300px',
    },
  ];

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const getBasicPayInfo = async () => {
    const response = await callApi({
      url: 'cost-management/basic-cost',
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      setOriginData(result.workspace_info_list);
      setTableData(result.workspace_info_list);
      setBasicInfo({
        activeWorkspace: result.basic_cost_info.active,
        member: result.basic_cost_info.members,
        workspaceBasicFee: result.basic_cost_info.time_unit_cost,
        timeUnit: result.basic_cost_info.time_unit,
        addMemberCost: result.basic_cost_info.add_member_cost,
        outBoundNetwork: result.basic_cost_info.out_bound_network,
      });
    }
  };

  useEffect(() => {
    getBasicPayInfo();
  }, []);

  return (
    <AdminBasicBillingContent
      keyword={keyword}
      searchKey={searchKey}
      loading={loading}
      columns={columns}
      tableData={tableData}
      basicInfo={basicInfo}
      onSortHandler={onSortHandler}
    />
  );
};

export default AdminBasicBillingPage;
