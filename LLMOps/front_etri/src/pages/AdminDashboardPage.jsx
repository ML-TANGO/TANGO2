import { Tooltip } from '@tango/ui-react';

import { loadModalComponent } from '@src/modal';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useHistory } from 'react-router-dom';

// Components
import AdminDashboardContent from '@src/components/pageContents/admin/AdminDashboardContent';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

function AdminDashboardPage() {
  const history = useHistory();
  const { t } = useTranslation();

  const [totalCount, setTotalCount] = useState([
    {
      variation: 0,
      total: '-',
      name: 'Workspaces',
    },
    {
      variation: 0,
      total: '-',
      name: 'Trainings',
    },
    {
      variation: 0,
      total: '-',
      name: 'Deployments',
    },
    {
      variation: 0,
      total: '-',
      name: 'Docker Images',
    },
    {
      variation: 0,
      total: '-',
      name: 'Datasets',
    },
    {
      variation: 0,
      total: '-',
      name: 'Nodes',
    },
  ]);
  const [gpuUsageByType, setGpuUsageByType] = useState(null);
  const [gpuUsageByGuarantee, setGpuUsageByGuarantee] = useState(null);
  const [hddUsage, setHddUsage] = useState({ used: '-', total: '-' });
  const [historyData, setHistoryData] = useState([]);
  const [serverError, setServerError] = useState(false);
  const [storageTotalData, setStorageTotalData] = useState(null);
  const [storageTableData, setStorageTableData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [totalUsage, setTotalUsage] = useState({
    cpu: null,
    gpu: null,
    ram: null,
    storage_data: null,
    storage_main: null,
  });

  /**
   * 파이차트 데이터 파싱
   *
   * @param {object} data 차트 데이터
   * @param {string} chartTitle 차트 제목
   */
  const parsePieChartData = useCallback(
    (data, chartTitle) => {
      const dataKeys = Object.keys(data);
      const result = [];
      for (let i = 0; i < dataKeys.length; i += 1) {
        const title = dataKeys[i];
        if (title !== 'total') {
          result.push({
            title: `${title}.label`,
            value: data[title],
            icon: title === 'over_limit' && (
              <Tooltip
                contentsCustomStyle={{ width: '400px' }}
                contents={
                  <>
                    <p>{t('causeOfcollision.title.label')}</p>
                    <span>
                      {t('causeOfcollision.m1.message')}
                      <br />
                      {t('causeOfcollision.m2.message')}
                      <br />
                      {t('causeOfcollision.m3.message')}
                      <br />
                    </span>
                    <p>{t('solutionOfcollision.title.label')}</p>
                    <span>
                      {t('solutionOfcollision.m1.message')}
                      <br />
                      {t('solutionOfcollision.m2.message')}
                      <br />
                      {t('solutionOfcollision.m3.message')}
                      <br />
                    </span>
                  </>
                }
              >
                <img
                  style={{ marginLeft: '4px' }}
                  src='/images/icon/error-o.svg'
                  alt='deleted'
                />
              </Tooltip>
            ),
          });
        }
      }
      return { chartData: result, total: data.total, chartTitle };
    },
    [t],
  );

  /**
   * API 호출 GET
   * 어드민 대시보드 데이터 가져오기
   * totalcount, usage, history, timeline
   */
  const getDashboardData = useCallback(async () => {
    const response = await callApi({
      url: 'dashboard/admin',
      method: 'GET',
    });

    const timelineResponse = await callApi({
      url: 'dashboard/admin/resource-usage',
      method: 'GET',
    });

    const { result, status, message, error } = response;
    const { result: timelineResult } = timelineResponse;

    if (status === STATUS_SUCCESS) {
      setServerError(false);
      const { totalCount, usage, history } = result;

      const { timeline } = timelineResult;

      setTotalCount(totalCount);
      setHistoryData(history);
      setTotalUsage(timeline);
      if (usage) {
        const _parsePieChartData = parsePieChartData(
          usage.gpuByType,
          'gpuUsageByType.title.label',
        );
        setGpuUsageByType(_parsePieChartData);
        const _gpuUsageByGuarantee = parsePieChartData(
          usage.gpuByGuarantee,
          'gpuUsageByGuarantee.title.label',
        );
        setGpuUsageByGuarantee(_gpuUsageByGuarantee);
        setHddUsage(usage.hdd);
      }
    } else {
      setServerError(true);
      errorToastMessage(error, message);
    }
    setLoading(false);
  }, [parsePieChartData]);

  const getStorageData = useCallback(async () => {
    const response = await callApi({
      url: 'storage',
      method: 'get',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setStorageTotalData(result.total);
      setStorageTableData(result.list);
      if (!result.total || !result.list) {
        setStorageTotalData([]);
        setStorageTableData([]);
      }
    } else {
      setStorageTotalData([]);
      setStorageTableData([]);
      errorToastMessage(error, message);
    }
    setLoading(false);
  }, []);

  /**
   * 새로고침
   */
  const onRefresh = () => {
    setLoading(true);
    getDashboardData();
    getStorageData();
  };

  /**
   * 페이지 바로가기
   *
   * @param {string} path 페이지 이름
   */
  const directLink = (path) => {
    history.push(`/admin/${path}`);
  };

  useEffect(() => {
    loadModalComponent('ADD_STORAGE');
  }, []);

  useEffect(() => {
    getDashboardData();
    getStorageData();
  }, [getDashboardData, getStorageData]);

  return (
    <AdminDashboardContent
      totalCount={totalCount}
      history={historyData}
      hddUsage={hddUsage}
      onRefresh={onRefresh}
      serverError={serverError}
      gpuUsageByGuarantee={gpuUsageByGuarantee}
      gpuUsageByType={gpuUsageByType}
      directLink={directLink}
      storageTotalData={storageTotalData}
      storageTableData={storageTableData}
      loading={loading}
      totalUsage={totalUsage}
    />
  );
}

export default AdminDashboardPage;
