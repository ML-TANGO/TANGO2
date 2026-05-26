import { convertDuration } from '@src/datetimeUtils';

import { callApi } from '@src/network';

import { executeWithLogging } from '@src/utils';

export const getInstanceTableInfo = async (
  workspace,
  dateState,
  type,
  page,
  size,
  search_term,
  signal,
) => {
  if (!workspace) return;
  const { startDate, endDate } = dateState;

  const { result } = await callApi({
    url: 'records/utilization/history',
    method: 'get',
    params: {
      workspace_id: workspace.value === 9999 ? null : workspace.value,
      start_datetime: startDate,
      end_datetime: endDate,
      page,
      size,
      type: type === 'all' ? null : type,
      search_key: 'workspace',
      search_term,
    },
    signal,
  });
  return result;
};

export const handleExcelDownload = async (
  workspace,
  dateState,
  type,
  page,
  size,
  search_term,
  button,
  setExcelData,
  t,
) => {
  await executeWithLogging(async () => {
    const result = await getInstanceTableInfo(
      workspace,
      dateState,
      type,
      page,
      size,
      search_term,
    );
    const { histories } = result;

    const excelList = histories.map((el) => {
      const {
        workspace_name,
        type_detail,
        node_name,
        start_datetime,
        end_datetime,
        period,
      } = el;
      return [
        workspace_name,
        type_detail,
        node_name,
        start_datetime,
        end_datetime,
        convertDuration(period),
      ];
    });
    excelList.unshift([
      t('workspace'),
      t('type.label'),
      t('projectName.label'),
      t('startTime.label'),
      t('stopTime.label'),
      t('uptime.label'),
    ]);

    setExcelData(
      [
        {
          columns: new Array(excelList.length).fill(''),
          data: excelList,
        },
      ],
      () => {
        button.click();
      },
    );
  });
};
