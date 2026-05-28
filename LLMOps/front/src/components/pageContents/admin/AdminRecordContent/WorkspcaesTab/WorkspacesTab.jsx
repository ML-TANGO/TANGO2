import { Selectbox } from '@jonathan/ui-react';

// custom hooks
import { useStateCallback } from '@src/customHooks';
// Utils
import { convertLocalTime, now } from '@src/datetimeUtils';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { withTranslation } from 'react-i18next';

import Table from '@src/components/molecules/Table';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import RecordsNav from '../RecordsNav';

// CSS module
import classNames from 'classnames/bind';
import style from './WorkspacesTab.module.scss';

const cx = classNames.bind(style);

const WorkspacesTab = ({ t, navList }) => {
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(1);
  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('timestamp.label')}
          idx={0}
        />
      ),
      selector: 'time_stamp',
      sortable: true,
      minWidth: '172px',
      maxWidth: '172px',
      cell: ({ time_stamp: timeStamp }) => convertLocalTime(timeStamp),
    },
    {
      name: t('workspace.label'),
      selector: 'workspace',
      minWidth: '392px',
      maxWidth: '392px',
      cell: ({ workspace }) => <div title={workspace}>{workspace}</div>,
    },
    {
      name: t('user.label'),
      selector: 'user',
      minWidth: '236px',
      maxWidth: '236px',
      cell: ({ user }) => <div title={user}>{user}</div>,
    },
    {
      name: t('task.label'),
      selector: 'task',
      minWidth: '208px',
      maxWidth: '208px',
      cell: ({ task }) => {
        let taskItem = '-';
        if (task === 'image') {
          taskItem = 'dockerImage.label';
        } else if (task === 'job') {
          taskItem = 'training/job.label';
        } else if (task === 'hyperparamsearch') {
          taskItem = 'training/hps.label';
        } else {
          taskItem = `${task}.label`;
        }
        return t(taskItem);
      },
    },
    {
      name: t('action.label'),
      selector: 'action',
      minWidth: '192px',
      maxWidth: '192px',
      cell: ({ action }) => t(`${action}.label`),
    },
    {
      name: t('taskName.label'),
      selector: 'task_name',
      minWidth: '192px',
      maxWidth: '192px',
      cell: ({ task_name: taskName }) => (
        <div title={taskName}>
          {taskName ? taskName.replaceAll('[advanced]', '[custom]') : '-'}
        </div>
      ),
    },
    {
      name: t('details.label'),
      selector: 'update_details',
      maxWidth: '200px',
      cell: ({ update_details: updateDetails }) => {
        return (
          <div title={updateDetails}>
            {updateDetails ? updateDetails.split('/').join(' / ') : '-'}
          </div>
        );
      },
    },
  ];

  // filter 설정
  const taskOptions = [
    { label: t('allTask.label'), value: 'all' },
    { label: t('workspace.label'), value: 'workspace' },
    { label: t('training.label'), value: 'training' },
    { label: t('training/job.label'), value: 'job' },
    { label: t('training/hps.label'), value: 'hyperparamsearch' },
    { label: t('deployment.label'), value: 'deployment' },
    { label: t('dockerImage.label'), value: 'image' },
    { label: t('dataset.label'), value: 'dataset' },
  ];

  const actionOptions = [
    { label: t('allAction.label'), value: 'all' },
    { label: t('create.label'), value: 'create' },
    { label: t('delete.label'), value: 'delete' },
    { label: t('update.label'), value: 'update' },
    { label: t('download.label'), value: 'download' },
    { label: t('upload.label'), value: 'upload' },
    { label: t('uploadData.label'), value: 'uploadData' },
    { label: t('deleteData.label'), value: 'deleteData' },
    { label: t('updateData.label'), value: 'updateData' },
  ];

  const searchOptions = [
    { label: t('workspace.label'), value: 'workspace' },
    { label: t('user.label'), value: 'user' },
    { label: t('taskName.label'), value: 'task_name' },
  ];

  const [tableData, setTableData] = useState([]);
  const [totalRow, setTotalRow] = useState(0);
  const [chipList, setChipList] = useState([]);
  const [searchParam, setSearchParam] = useState({
    page: 1,
    size: 10,
    task: { label: t('allTask.label'), value: 'all' },
    action: { label: t('allAction.label'), value: 'all' },
    searchKey: { label: t('workspace.label'), value: 'workspace' },
    keyword: '',
    sort_key: 'time_stamp',
    sort_value: 'desc',
  });
  const [excelData, setExcelData] = useStateCallback([]);

  const getWorkspaceUsageRecords = useCallback(async () => {
    const queryParam = [];
    const monthsParam = [];
    const workspacesParam = [];
    for (let i = 0; i < chipList.length; i += 1) {
      const {
        param: { key, value },
      } = chipList[i];
      switch (key) {
        case 'year':
          queryParam.push(`${key}=${value}`);
          break;
        case 'months':
          if (value !== 'all') monthsParam.push(value);
          break;
        case 'workspaces':
          if (value !== 'all') workspacesParam.push(value);
          break;
        default:
      }
    }
    if (monthsParam.length !== 0) {
      queryParam.push(`months=${monthsParam.join(',')}`);
    }
    if (workspacesParam.length !== 0) {
      queryParam.push(`workspace_ids=${workspacesParam.join(',')}`);
    }
    const {
      page,
      size,
      keyword,
      searchKey,
      action,
      task,
      sort_key: sortKey,
      sort_value: sortValue,
    } = searchParam;
    let url = `records/workspaces?page=${page}&size=${size}${
      queryParam.length !== 0 ? `&${queryParam.join('&')}` : ''
    }`;
    if (action.value !== 'all') url += `&action=${action.value}`;
    if (task.value !== 'all') url += `&task=${task.value}`;
    if (keyword !== '')
      url += `&search_key=${searchKey.value}&search_value=${keyword}`;
    url += `&sort=${sortKey}&order=${sortValue}`;
    const response = await callApi({
      url,
      method: 'get',
    });
    const { result, status } = response;
    if (status === STATUS_SUCCESS) {
      const { list, total } = result;
      setTableData(list);
      setTotalRow(total);
    } else {
      setTableData([]);
    }
  }, [searchParam, setTotalRow, setTableData, chipList]);

  // 설정한 조건으로 workspace 목록 조회
  const onSearch = useCallback(
    (chips) => {
      setChipList(chips);
    },
    [setChipList],
  );

  // 테이블 페이지 이동
  const onChangePage = useCallback(
    (page) => {
      setSearchParam({
        ...searchParam,
        page,
      });
    },
    [searchParam, setSearchParam],
  );

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    onChangeSearchKeyword({ target: { value: '' } });
  };

  // 테이블 한번에 볼 갯수 변경
  const onChangeRowsPerPage = useCallback(
    (size) => {
      setSearchParam({
        ...searchParam,
        page: 1,
        size,
      });
    },
    [searchParam, setSearchParam],
  );

  // 필터 변경 이벤트
  const onChangeFilter = useCallback(
    (target, filter) => {
      setSearchParam({
        ...searchParam,
        [target]: filter,
      });
    },
    [setSearchParam, searchParam],
  );

  // 테이블 검색 이벤트
  const onChangeSearchKeyword = useCallback(
    (e) => {
      setSearchParam({
        ...searchParam,
        keyword: e.target.value,
      });
    },
    [setSearchParam, searchParam],
  );

  // sort
  const onSort = ({ selector }, sortDirection) => {
    setSearchParam({
      ...searchParam,
      sort_key: selector,
      sort_value: sortDirection,
    });
    onClickHandler(clickedIdx, sortDirection);
  };

  // 엑셀 다운로드 이벤트
  const excelDownload = useCallback(
    async (button) => {
      const queryParam = [];
      const monthsParam = [];
      const workspacesParam = [];
      let year = 'All';
      let workspaceValue = [];
      for (let i = 0; i < chipList.length; i += 1) {
        const {
          param: { key, value },
          origin: { label: wName },
        } = chipList[i];
        switch (key) {
          case 'year':
            year = value;
            queryParam.push(`${key}=${value}`);
            break;
          case 'months':
            if (value !== 'all') {
              monthsParam.push(value);
            }
            break;
          case 'workspaces':
            if (value !== 'all') {
              workspacesParam.push(value);
            }
            workspaceValue.push(wName);
            break;
          default:
        }
      }
      if (monthsParam.length !== 0) {
        queryParam.push(`months=${monthsParam.join(',')}`);
      }
      if (workspacesParam.length !== 0) {
        queryParam.push(`workspace_ids=${workspacesParam.join(',')}`);
      }
      const { keyword, searchKey, action, task } = searchParam;
      let url = `records/workspaces${
        queryParam.length !== 0 ? `?${queryParam.join('&')}` : ''
      }`;
      if (action.value !== 'all') url += `&action=${action.value}`;
      if (task.value !== 'all') url += `&task=${task.value}`;
      if (keyword !== '')
        url += `&searchKey=${searchKey.value}&keyword=${keyword}`;
      const response = await callApi({
        url,
        method: 'get',
      });
      const { result, status, error } = response;
      if (status === STATUS_SUCCESS) {
        const { list } = result;
        let monthValue = monthsParam.join(',');
        if (monthValue === '') monthValue = 'All';
        workspaceValue = workspaceValue.join(',');
        if (workspaceValue === '') workspaceValue = 'All';
        const excelResult = [
          {
            columns: new Array(5).fill(''),
            data: [
              [
                t('year.label'),
                year,
                t('month.label'),
                monthValue,
                t('workspaces.label'),
                workspaceValue,
              ],
              new Array(5).fill(''),
              [
                t('timestamp.label'),
                t('workspace.label'),
                t('user.label'),
                t('task.label'),
                t('taskName.label'),
                t('action.label'),
                t('details.label'),
              ],
              ...list.map(
                ({
                  time_stamp: timeStampItem,
                  workspace: workspaceItem,
                  user: userItem,
                  task: taskItem,
                  task_name: taksNameItem,
                  action: actionItem,
                  update_details: detailsItem,
                }) => [
                  timeStampItem,
                  workspaceItem,
                  userItem,
                  taskItem,
                  taksNameItem,
                  actionItem,
                  detailsItem,
                ],
              ),
            ],
          },
        ];

        setExcelData(excelResult, () => {
          button.click();
        });
        // toast.success(t('excelExport.success.toast'));
      } else {
        errorToastMessage(error, t('excelExport.error.toast'));
      }
    },
    [searchParam, chipList, setExcelData, t],
  );

  useEffect(() => {
    getWorkspaceUsageRecords();
  }, [getWorkspaceUsageRecords]);

  const { task, action, searchKey, keyword } = searchParam;

  const filterList = (
    <>
      <div className={cx('selectbox')}>
        <Selectbox
          list={taskOptions}
          selectedItem={task}
          onChange={(d) => {
            onChangeFilter('task', d);
          }}
          customStyle={{
            fontStyle: {
              selectbox: {
                fontSize: '14px',
              },
            },
          }}
        />
      </div>
      <div className={cx('selectbox')}>
        <Selectbox
          list={actionOptions}
          selectedItem={action}
          onChange={(d) => {
            onChangeFilter('action', d);
          }}
          customStyle={{
            fontStyle: {
              selectbox: {
                fontSize: '14px',
              },
            },
          }}
        />
      </div>
    </>
  );

  return (
    <div id='workspace-tab'>
      <RecordsNav
        navList={navList}
        handleExcelDownLoad={excelDownload}
        excelDataFormat={{
          sheetName: t('workspaceUsageRecords.title.label'),
          sheetData: excelData,
        }}
        excelFileName={`${t('workspaceUsageRecords.file.label')}_${now()}`}
        pdfTargetId='workspace-tab'
        // isExportBtn
      />
      <Table
        columns={columns}
        data={tableData}
        totalRows={parseInt(totalRow)}
        selectableRows={false}
        paginationServer
        onChangeRowsPerPage={onChangeRowsPerPage}
        onChangePage={onChangePage}
        defaultSortField='time_stamp'
        toggledClearRows={false}
        hideButtons
        filterList={filterList}
        searchOptions={searchOptions}
        searchKey={searchKey}
        keyword={keyword}
        onSearchKeyChange={(d) => {
          onChangeFilter('searchKey', d);
        }}
        onSearch={onChangeSearchKeyword}
        sortServer
        onChangeSort={onSort}
        onClear={onClear}
        handleRefresh={getWorkspaceUsageRecords}
      />
    </div>
  );
};

export default withTranslation()(WorkspacesTab);
