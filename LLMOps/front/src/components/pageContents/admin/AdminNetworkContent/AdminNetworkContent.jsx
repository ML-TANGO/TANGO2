import { useState, useEffect, useCallback } from 'react';
import _ from 'lodash';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, Selectbox } from '@jonathan/ui-react';
import PageTitle from '@src/components/atoms/PageTitle';
import Table from '@src/components/molecules/Table';
import Tab from '@src/components/molecules/Tab';
import AdminNetworkDetail from './AdminNetworkDetail';

// CSS module
import style from './AdminNetworkContent.module.scss';
import classNames from 'classnames/bind';

const cx = classNames.bind(style);

function AdminNetworkContent({
  groupViewData,
  columns,
  tableData,
  totalRows,
  onStatusFilterChange,
  statusFilter,
  onCategoryFilterChange,
  categoryFilter,
  searchKey,
  onSearchKeyChange,
  keyword,
  onSearch,
  onSelect,
  onClear,
  toggledClearRows,
  onCreate,
  deleteBtnDisabled,
  openDeleteConfirmPopup,
  onSortHandler,
}) {
  const { t } = useTranslation();

  // 그룹 뷰 데이터
  const ethernetAllocated = groupViewData?.ethernet.allocated_nodes;
  const ethernetUnallocated = groupViewData?.ethernet.unallocated_nodes;
  const ethernetNetworkGroupList = groupViewData?.ethernet.network_group_list;
  const infinibandAllocated = groupViewData?.infiniband.allocated_nodes;
  const infinibandUnallocated = groupViewData?.infiniband.unallocated_nodes;
  const infinibandNetworkGroupList =
    groupViewData?.infiniband.network_group_list;
  const targetOptions = [
    { label: t('all.label'), value: 'all' },
    { label: t('infiniBand.label'), value: 'infiniband' },
    { label: t('ethernet.label'), value: 'ethernet' },
  ];
  const [target, setTarget] = useState(targetOptions[0]);
  const [allocatedData, setAllocatedData] = useState([]);
  const [unallocatedData, setUnallocatedData] = useState([]);
  const [networkGroupList, setNetworkGroupList] = useState([]);

  const targetChangeHandler = useCallback(
    ({ label, value }) => {
      setTarget({ label, value });
      if (value === 'ethernet') {
        setAllocatedData(ethernetAllocated);
        setUnallocatedData(ethernetUnallocated);
        setNetworkGroupList(ethernetNetworkGroupList);
      } else if (value === 'infiniband') {
        setAllocatedData(infinibandAllocated);
        setUnallocatedData(infinibandUnallocated);
        setNetworkGroupList(infinibandNetworkGroupList);
      } else {
        // 전체
        let allocatedAll = [...ethernetAllocated, ...infinibandAllocated];
        let unallocatedAll = [...ethernetUnallocated, ...infinibandUnallocated];
        // 인피니밴드, 이더넷 둘 다 배정된 노드 중복 제거
        allocatedAll = _.uniqBy([...allocatedAll], 'node_id');
        // 인피니밴드, 이더넷 둘 중 어디에도 배정되지 않은 노드 찾기
        // 중복 제거 후, 둘 중 하나라도 배정된 노드 필터
        unallocatedAll = _.uniqBy([...unallocatedAll], 'node_id');
        unallocatedAll = unallocatedAll.filter((item) => {
          return !allocatedAll
            .map((item2) => {
              return item2.node_id;
            })
            .includes(item.node_id);
        });
        setAllocatedData(allocatedAll);
        setUnallocatedData(unallocatedAll);
        setNetworkGroupList([
          ...ethernetNetworkGroupList,
          ...infinibandNetworkGroupList,
        ]);
      }
    },
    [
      ethernetAllocated,
      ethernetNetworkGroupList,
      ethernetUnallocated,
      infinibandAllocated,
      infinibandNetworkGroupList,
      infinibandUnallocated,
    ],
  );

  const searchOptions = [
    { label: 'network.groupName.label', value: 'name' },
    { label: 'description.label', value: 'description' },
  ];

  const statusFilterOptions = [
    {
      label: 'allStatus.label',
      value: 'all',
    },
    {
      label: 'available.label',
      value: true,
    },
    {
      label: 'unavailable.label',
      value: false,
    },
  ];

  const categoryFilterOptions = [
    { label: 'allCategory.label', value: 'all' },
    { label: 'infiniBand.label', value: 1 },
    { label: 'ethernet.label', value: 0 },
  ];

  const filterList = (
    <>
      <Selectbox
        size='medium'
        list={statusFilterOptions}
        selectedItem={statusFilter}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onStatusFilterChange}
        t={t}
      />
      <Selectbox
        size='medium'
        list={categoryFilterOptions}
        selectedItem={categoryFilter}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onCategoryFilterChange}
        t={t}
      />
    </>
  );
  const topButtonList = (
    <>
      <Button type='primary' onClick={onCreate}>
        {t('network.create.group.label')}
      </Button>
    </>
  );

  const bottomButtonList = (
    <>
      <Button
        type='red'
        onClick={openDeleteConfirmPopup}
        disabled={deleteBtnDisabled}
      >
        {t('delete.label')}
      </Button>
    </>
  );

  const ExpandedComponent = (row) => {
    return <AdminNetworkDetail data={row.data} />;
  };

  useEffect(() => {
    if (groupViewData) {
      targetChangeHandler({ label: 'all.label', value: 'all' });
    }
  }, [groupViewData, targetChangeHandler]);

  return (
    <div id='AdminNetworkContent'>
      <PageTitle>{t('network.label')}</PageTitle>
      <div className={cx('content')}>
        <div className={cx('group-view')}>
          <Tab
            type='c'
            option={targetOptions}
            select={target}
            tabHandler={targetChangeHandler}
            backgroudColor='#fff'
            sidePaddingNone
          />
          <div className={cx('tab-container')}>
            <div className={cx('status')}>
              <h3 className={cx('title')}>{t('network.view.status.title')}</h3>
              <div className={cx('group-wrapper', 'allocated')}>
                <label className={cx('label')}>
                  {t('network.view.allocated.label')}
                </label>
                <div className={cx('nodes')}>
                  {allocatedData?.length > 0 ? (
                    allocatedData?.map(
                      ({ node_id: nodeId, node_name: nodeName }) => {
                        return (
                          <div
                            key={`allocated-${target.value}-${nodeId}`}
                            className={cx('node')}
                          >
                            {nodeName}
                          </div>
                        );
                      },
                    )
                  ) : (
                    <div className={cx('empty-message')}>
                      {t('network.view.allocated.empty.message')}
                    </div>
                  )}
                </div>
              </div>
              <div className={cx('group-wrapper', 'unallocated')}>
                <label className={cx('label')}>
                  {t('network.view.unallocated.label')}
                </label>
                <div className={cx('nodes')}>
                  {unallocatedData?.length > 0 ? (
                    unallocatedData?.map(
                      ({ node_id: nodeId, node_name: nodeName }) => {
                        return (
                          <div
                            key={`unallocated-${target.value}-${nodeId}`}
                            className={cx('node')}
                          >
                            {nodeName}
                          </div>
                        );
                      },
                    )
                  ) : (
                    <div className={cx('empty-message')}>
                      {t('network.view.unallocated.empty.message')}
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className={cx('nodes-by-group')}>
              <h3 className={cx('title')}>
                {t('network.view.nodesByGroup.title')}
              </h3>
              <div className={cx('info')}>
                <span className={cx('multi-port')}></span>: Multi-port
              </div>
              <div className={cx('group-wrapper')}>
                {networkGroupList?.length > 0 ? (
                  networkGroupList?.map(
                    ({
                      id,
                      belonging_nodes: nodes,
                      network_group_name: networkGroupName,
                    }) => {
                      return (
                        <div key={id} className={cx('group-box')}>
                          <label className={cx('label')}>
                            {networkGroupName}
                          </label>
                          <div className={cx('nodes')}>
                            {nodes?.length > 0 ? (
                              nodes.map(
                                ({
                                  node_id: nodeId,
                                  node_name: nodeName,
                                  is_multi_port: isMultiPort,
                                }) => {
                                  return (
                                    <div
                                      key={`group-${target.value}-${nodeId}`}
                                      className={cx(
                                        'node',
                                        isMultiPort && 'multi-port',
                                      )}
                                    >
                                      {nodeName}
                                    </div>
                                  );
                                },
                              )
                            ) : (
                              <div className={cx('empty-message')}>
                                {t('network.view.nodesByGroup.empty.message')}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    },
                  )
                ) : (
                  <div className={cx('empty-message')}>
                    {t('network.view.group.empty.message')}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        <Table
          columns={columns}
          data={tableData}
          totalRows={totalRows}
          topButtonList={topButtonList}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          ExpandedComponent={ExpandedComponent}
          onSelect={onSelect}
          onClear={onClear}
          defaultSortField='create_datetime'
          toggledClearRows={toggledClearRows}
          selectableRowDisabled={({ type }) => type === 0}
          filterList={filterList}
          searchOptions={searchOptions}
          searchKey={searchKey}
          keyword={keyword}
          onSearchKeyChange={onSearchKeyChange}
          onSearch={(e) => {
            onSearch(e.target.value);
          }}
          onSortHandler={onSortHandler}
        />
      </div>
    </div>
  );
}

export default AdminNetworkContent;
