import { useStateCallback } from '@src/customHooks';
import { now } from '@src/datetimeUtils';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation, withTranslation } from 'react-i18next';

import { callApi } from '@src/network';
import { executeWithLogging, getDateRange } from '@src/utils';
import { handleExcelDownload } from './util';

import RecordsNav from '../RecordsNav';
import InstanceAllocateRecord from './InstanceAllocateRecord';
import InstanceSearch from './InstanceSearch';
import InstanceTable from './InstanceTable';
import ResourceUsageGraph from './ResourceUsageGraph';

const initialInstanceObj = {
  workspace_name: '-',
  start_datetime: '-',
  end_datetime: '-',
  instances: [
    {
      instance_info: {
        instance_name: '-',
        instance_count: '',
      },
    },
  ],
};

const initialInstanceAllocationData = [
  initialInstanceObj,
  initialInstanceObj,
  initialInstanceObj,
  initialInstanceObj,
  initialInstanceObj,
];

const initialStorageObj = {
  storage_name: '-',
  storage_utilization: 0,
};
const initialStorageData = [
  initialStorageObj,
  initialStorageObj,
  initialStorageObj,
];

const initialInstanceUsageObj = {
  instance_name: '-',
  instance_time: 0,
};
const initialInstanceUsageList = [
  initialInstanceUsageObj,
  initialInstanceUsageObj,
  initialInstanceUsageObj,
];

const initialSummaryInfo = {
  summary: {
    activation_time: null,
    storage_usage: initialStorageData,
    instance_usage: initialInstanceUsageList,
  },
  instance_allocation_histories: initialInstanceAllocationData,
};

const InstanceTab = ({ navList }) => {
  const { t } = useTranslation();

  // ** [워크스페이스 관련] 함수 및 상태**
  const [workspace, setWorkspace] = useState(null);
  const [workspaceOptions, setWorkspaceOptions] = useState([]);
  const handleWorkspace = useCallback(
    (value) => {
      setWorkspace(value);
    },
    [setWorkspace],
  );

  // ** [날짜 관련] 함수 및 상태 **
  const { startDate, endDate } = getDateRange();
  const [dateState, setDateState] = useState({
    startDate,
    endDate,
  });
  const handleCalendar = useCallback((from, to, setDateState) => {
    setDateState({
      startDate: from,
      endDate: to,
    });
  }, []);

  const [excelData, setExcelData] = useStateCallback([]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    // workspace 옵션 목록 조회
    const getWorkspaceOptions = async () => {
      executeWithLogging(async () => {
        const { result } = await callApi({
          url: 'records/options/workspaces',
          method: 'get',
          signal,
        });

        if (result) {
          const shallowCopyWorkspaceList = result.slice();
          shallowCopyWorkspaceList.unshift({
            name: 'All',
            id: 9999,
          });

          if (shallowCopyWorkspaceList.length !== 0) {
            setWorkspace({
              label: shallowCopyWorkspaceList[0].name,
              value: shallowCopyWorkspaceList[0].id,
            });
          }
          setWorkspaceOptions([
            ...shallowCopyWorkspaceList.map(({ id, name }) => ({
              label: name,
              value: id,
              checked: false,
            })),
          ]);
        }
      });
    };

    getWorkspaceOptions();

    return () => controller.abort();
  }, []);

  const [instanceSummaryInfo, setInstanceSummaryInfo] =
    useState(initialSummaryInfo);
  const { instance_allocation_histories, summary } = instanceSummaryInfo;

  const isLoading = useRef(true);
  const getRecordUtilizationInfo = useCallback(async () => {
    await executeWithLogging(async () => {
      const { result } = await callApi({
        url: 'records/utilization/info',
        params: {
          workspace_id: workspace.value === 9999 ? null : workspace.value,
        },
      });
      setInstanceSummaryInfo(result);
      isLoading.current = false;
    });
  }, [workspace]);

  useEffect(() => {
    if (!workspace) return;
    getRecordUtilizationInfo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  return (
    <div id='resource-tab'>
      <RecordsNav
        navList={navList}
        handleExcelDownLoad={(button) =>
          handleExcelDownload(
            workspace,
            dateState,
            { value: 'all' },
            null,
            99999,
            null,
            button,
            setExcelData,
            t,
          )
        }
        excelDataFormat={{
          sheetName: t('resourceUsageRecords.label'),
          sheetData: excelData,
        }}
        excelFileName={`${workspace ? `[${workspace.label}]` : ''} ${t(
          'resourceUsageRecords.file.label',
        )}_${now()}`}
        pdfTargetId='resource-tab'
        isExportBtn
      />
      <InstanceSearch
        dateState={dateState}
        selectedWorkspaceValue={workspace}
        workspaceOptions={workspaceOptions}
        handleWorkspace={(v) => handleWorkspace(v)}
        handleCalendar={(from, to) => handleCalendar(from, to, setDateState)}
      />
      <InstanceAllocateRecord
        workspaceId={workspace && workspace.value}
        summary={summary}
        isLoading={isLoading.current}
        instance_allocation_histories={instance_allocation_histories}
      />
      <ResourceUsageGraph
        workspaceId={workspace && workspace.value}
        isLoading={isLoading.current}
        dateState={dateState}
      />
      <InstanceTable
        workspace={workspace}
        workspaceOptions={workspaceOptions}
        dateState={dateState}
      />
    </div>
  );
};
export default withTranslation()(InstanceTab);
