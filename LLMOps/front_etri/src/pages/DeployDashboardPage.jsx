// Date Time Utils
import {
  DATE_FORM,
  DATE_TIME_FORM,
  getUTCTime,
  TODAY,
} from '@src/datetimeUtils';
import dayjs from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useParams, useRouteMatch } from 'react-router-dom';

// Components
import DeployDashboardContent from '@src/components/pageContents/user/DeployDashboardContent';
import { toast } from '@src/components/Toast';

// Actions
import { startPath } from '@src/store/modules/breadCrumb';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function DeployDashboardPage() {
  // i18n
  const { t } = useTranslation();

  // Router Hooks
  const { did } = useParams();
  const match = useRouteMatch();
  const { id: wid } = match.params;

  // Redux Hooks
  const dispatch = useDispatch();

  const [title, setTitle] = useState('');
  // Component State
  const [mount, setMount] = useState(false);
  const [loading, setLoading] = useState(false);
  const [totalInfoData, setTotalInfoData] = useState({
    total_call_count: 0,
    total_success_rate: 0,
    total_log_size: 0,
    running_worker_count: 0,
    error_worker_count: 0,
    deployment_run_time: 0,
  });
  const [resourceInfoData, setResourceInfoData] = useState({
    cpu_usage_rate: {
      min: 0,
      max: 0,
      average: 0,
    },
    ram_usage_rate: {
      min: 0,
      max: 0,
      average: 0,
    },
    gpu_core_usage_rate: {
      min: 0,
      max: 0,
      average: 0,
    },
    gpu_mem_usage_rate: {
      min: 0,
      max: 0,
      average: 0,
    },
    gpu_total_mem: 0,
    gpu_use_mem: 0,
    gpu_mem_unit: 'MiB',
  });
  const [searchResultInfoData, setSearchResultInfoData] = useState({});
  const [chartData, setChartData] = useState([]);
  const [statusCodeData, setStatusCodeData] = useState({
    200: {},
    300: {},
    400: {},
    500: {},
    rest: {},
  });
  const [errorRecordData, setErrorRecordData] = useState([]);
  const [searchType, setSearchType] = useState('range');
  const [startDate, setStartDate] = useState(dayjs().format(DATE_FORM));
  const [endDate, setEndDate] = useState(dayjs().format(DATE_FORM));
  const [minDate, setMinDate] = useState(dayjs().format(DATE_FORM));
  const [workerStartDate, setWorkerStartDate] = useState(dayjs());
  const [prevWorkerStartDate, setPrevWorkerStartDate] = useState(dayjs());
  const [historyGraphData, setHistoryGraphData] = useState({});
  const [selectedGraph, setSelectedGraph] = useState({
    cpu: true,
    ram: true,
    gpuCore: true,
    gpuMem: true,
    callCnt: true,
    abProcess: true,
    processTime: true,
    response: true,
    worker: true,
  });
  const [selectedGraphPer, setSelectedGraphPer] = useState({
    processTime: {
      selected: 'median',
      value: 0,
    },
    responseTime: {
      selected: 'median',
      value: 0,
    },
  });
  const [resolution, setResolution] = useState({
    label: 'Day',
    value: 60 * 60 * 24,
    isDisable: false,
  });
  const [resolutionList, setResolutionList] = useState([
    {
      label: ['10', 'minute.label'],
      value: 60 * 10,
      isDisable: false,
    },
    {
      label: ['1', 'hour.label'],
      value: 60 * 60,
      isDisable: false,
    },
    {
      label: ['4', 'hour.label'],
      value: 60 * 60 * 4,
      isDisable: false,
    },
    { label: 'day.label', value: 60 * 60 * 24, isDisable: false },
    { label: 'week.label', value: 60 * 60 * 24 * 7, isDisable: false },
    { label: 'month.label', value: 60 * 60 * 24 * 30, isDisable: false },
  ]);
  const [workers, setWorkers] = useState({ label: 'all.label' });
  const [workerList, setWorkerList] = useState([
    { label: 'all.label', value: 'all', checked: true },
  ]);
  const [logDownOptions, setLogDownOptions] = useState({
    nginx: true,
    api: true,
  });

  /**
   * ChartControlbox procesTime, responseTime list
   */
  const processTimeResponseTimeList = useMemo(
    () => [
      {
        label: 'median.label',
        value: 0,
        addData: {
          value: 'median',
        },
      },
      {
        label: 'average.label',
        value: 1,
        addData: {
          value: 'average',
        },
      },
      {
        label: '99percentile.label',
        value: 2,
        addData: {
          value: '99',
        },
      },
      {
        label: '95percentile.label',
        value: 3,
        addData: {
          value: '95',
        },
      },
      {
        label: '90percentile.label',
        value: 4,
        addData: {
          value: '90',
        },
      },
    ],
    [],
  );

  /**
   * 단위 선택 핸들러
   * @param {string} value Resolution 값
   */
  const onChangeResolution = (value) => {
    setResolution(value);
  };

  /**
   * 기간에 따른 단위 변경 함수
   * @param {object} startDate 시작 날짜
   * @param {object} endDate 끝 날짜
   */
  const changeResolutionListByRange = useCallback(
    (startDate, endDate) => {
      const startTime = dayjs(startDate).format(`${DATE_FORM} 00:00:00`);
      const endTime = dayjs(endDate).format(`${DATE_FORM} 23:59:59`);
      const duration = dayjs(endTime).diff(dayjs(startTime), 'seconds') + 1;

      let newResolutionList = [
        {
          label: ['10', 'minute.label'],
          value: 60 * 10,
          isDisable: false,
        },
        {
          label: ['1', 'hour.label'],
          value: 60 * 60,
          isDisable: false,
        },
        {
          label: ['4', 'hour.label'],
          value: 60 * 60 * 4,
          isDisable: false,
        },
        { label: 'day.label', value: 60 * 60 * 24, isDisable: false },
        { label: 'week.label', value: 60 * 60 * 24 * 7, isDisable: false },
        {
          label: 'month.label',
          value: 60 * 60 * 24 * 30,
          isDisable: false,
        },
      ];

      let disabledIndex = [];
      let defaultResolution = { ...resolution };

      if (duration <= 1 * 24 * 60 * 60) {
        // disable: Day, Week, Month
        disabledIndex = [3, 4, 5];
        defaultResolution = newResolutionList[0];
      } else if (1 * 24 * 60 * 60 < duration && duration <= 3 * 24 * 60 * 60) {
        // disable: Week, Month
        disabledIndex = [4, 5];
        defaultResolution = newResolutionList[0];
      } else if (3 * 24 * 60 * 60 < duration && duration <= 13 * 24 * 60 * 60) {
        // disable: 10min, Week, Month
        disabledIndex = [0, 4, 5];
        defaultResolution = newResolutionList[1];
      } else if (
        13 * 24 * 60 * 60 < duration &&
        duration <= 14 * 24 * 60 * 60
      ) {
        // disable: 10min, Month
        disabledIndex = [0, 5];
        defaultResolution = newResolutionList[1];
      } else if (
        14 * 24 * 60 * 60 < duration &&
        duration <= 59 * 24 * 60 * 60
      ) {
        // disable: 10min, 1h, Month
        disabledIndex = [0, 1, 5];
        defaultResolution = newResolutionList[2];
      } else if (
        59 * 24 * 60 * 60 < duration &&
        duration <= 100 * 24 * 60 * 60
      ) {
        // disable: 10min, 1h
        disabledIndex = [0, 1];
        defaultResolution = newResolutionList[2];
      } else if (
        100 * 24 * 60 * 60 < duration &&
        duration <= 365 * 24 * 60 * 60
      ) {
        // disable: 10min, 1h, 4h
        disabledIndex = [0, 1, 2];
        defaultResolution = newResolutionList[3];
      } else if (365 * 24 * 60 * 60 < duration) {
        // disable: 10min, 1h, 4h, Day
        disabledIndex = [0, 1, 2, 3];
        defaultResolution = newResolutionList[4];
      }
      disabledIndex.map((value) => {
        newResolutionList[value].isDisable = true;
        return newResolutionList;
      });
      setResolutionList(newResolutionList);
      setResolution(defaultResolution);
    },
    [resolution],
  );

  /**
   * 워커 변경 이벤트 핸들러
   */
  const onChangeWorker = (opt) => {
    const newOpt = opt.filter(({ checked }) => checked);
    setWorkerList(opt);
    let selectedWorker = { label: '' };
    if (opt[0].checked) {
      selectedWorker = { label: 'all.label' };
    } else if (newOpt.length === 1) {
      selectedWorker = { label: `1 ${t('worker.label')}` };
    } else {
      selectedWorker = { label: `${newOpt.length} ${t('workers.label')}` };
    }
    setWorkers(selectedWorker);
  };

  /**
   * 날짜 설정에 따라 워커 리스트 받아오기
   * @param {object} startDate 시작 날짜
   * @param {object} endDate 끝 날짜
   * @returns
   */
  const getWorkerList = useCallback(
    async (startDate, endDate) => {
      const startTime = dayjs(startDate).format(`${DATE_FORM} 00:00:00`);
      const endTime = dayjs(endDate).format(`${DATE_FORM} 23:59:59`);
      const query = `deployment_id=${did}&start_time=${startTime}&end_time=${endTime}`;

      const res = await callApi({
        url: `deployments/dashboard_options?${query}`,
        method: 'get',
      });
      const { result, status, message, error } = res;
      if (status === STATUS_SUCCESS) {
        const newWorkerList = result.deployment_running_worker.map((worker) => {
          return {
            label: ['worker.label', worker],
            value: worker,
            checked: true,
          };
        });
        newWorkerList.unshift({
          label: 'all.label',
          value: 'all',
          checked: true,
        });
        setWorkerList(newWorkerList);
        return true;
      }
      errorToastMessage(error, message);
      return false;
    },
    [did],
  );

  /**
   * 날짜(Range) 변경 이벤트 핸들러
   * @param {object} from 시작 날짜
   * @param {object} to 끝 날짜
   */
  const onChangeDate = useCallback(
    (from, to) => {
      const fromDate = dayjs(from);
      const toDate = dayjs(to);
      const isChange = fromDate.isAfter(toDate);
      if (isChange) {
        setStartDate(dayjs(to).format(DATE_FORM));
        setEndDate(dayjs(from).format(DATE_FORM));
      } else {
        setStartDate(dayjs(from).format(DATE_FORM));
        setEndDate(dayjs(to).format(DATE_FORM));
      }
      changeResolutionListByRange(from, to);
      getWorkerList(from, to);
    },
    [changeResolutionListByRange, getWorkerList],
  );

  /**
   * 콜 로그 다운로드 - 체크 여부 boolean값 변경 핸들러 (nginx, api)
   * @param {string} option
   */
  const logDownOptionsHandler = (option) => {
    setLogDownOptions({ ...logDownOptions, [option]: !logDownOptions[option] });
  };

  /**
   * 콜 로그 다운로드
   */
  const onDownloadCallLogs = async () => {
    const startTime = dayjs(startDate).format(`${DATE_FORM} 00:00:00`);
    const endTime = dayjs(endDate).format(`${DATE_FORM} 23:59:59`);
    const nginx = logDownOptions.nginx;
    const api = logDownOptions.api;
    const selectedWorkerList = workerList
      .filter(({ value, checked }) => value !== 'all' && checked)
      .map(({ value }) => value)
      .join(',');
    let query = `deployment_id=${did}&start_time=${startTime}&end_time=${endTime}`;
    if (selectedWorkerList.length > 0) {
      query = `${query}&worker_list=${selectedWorkerList}`;
    }
    if (nginx) {
      query = `${query}&nginx_log=True`;
    }
    if (api) {
      query = `${query}&api_log=True`;
    }

    const response = await network.callApiWithPromise({
      url: `deployments/download_api_log?${query}`,
      method: 'get',
    });
    const { data, status, statusText, headers } = response;

    if (status === 200) {
      if (data.status === 0) {
        toast.error(data.message);
      } else {
        let fileName;
        const contentDisposition = headers['content-disposition']; // 파일 이름
        if (contentDisposition) {
          const [fileNameMatch] = contentDisposition
            .split(';')
            .filter((str) => str.includes('filename'));
          if (fileNameMatch) {
            [, fileName] = fileNameMatch.split('=');
          }
        }
        const blob = new Blob([data], { type: 'application/tar' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `[LOG]_${fileName}.tar`;
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        // toast.success(statusText);
      }
    } else {
      toast.error(statusText);
    }
  };

  /**
   * 비정상처리 기록 CSV 다운로드
   */
  const onDownloadErrorRecord = async () => {
    const startTime = dayjs(startDate).format(`${DATE_FORM} 00:00:00`);
    const endTime = dayjs(endDate).format(`${DATE_FORM} 23:59:59`);
    const selectedWorkerList = workerList
      .filter(({ value, checked }) => value !== 'all' && checked)
      .map(({ value }) => value)
      .join(',');

    let query = `deployment_id=${did}&start_time=${startTime}&end_time=${endTime}`;
    if (selectedWorkerList.length > 0) {
      query = `${query}&worker_list=${selectedWorkerList}`;
    }

    const response = await network.callApiWithPromise({
      url: `deployments/download_abnormal_record?${query}`,
      method: 'get',
    });
    const { data, status } = response;

    if (status === 200) {
      if (data.status === 0) {
        toast.error(data.message);
      } else {
        const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `[ErrorRecord] ${dayjs(startDate).format(
          'YYYYMMDD',
        )}-${dayjs(endDate).format('YYYYMMDD')}.csv`;
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        defaultSuccessToastMessage('download');
      }
    } else {
      toast.error('Download error');
    }
  };

  /**
   * Info 데이터 받아오기 (대시보드 상단에 카드로 표시)
   */
  const getInfoData = useCallback(async () => {
    const res = await callApi({
      url: `deployments/dashboard_status?deployment_id=${did}`,
      method: 'get',
    });
    const { result, status, message, error } = res;
    if (status === STATUS_SUCCESS) {
      const {
        total_info: total,
        resource_info: resource,
        worker_start_time: workerStartTime,
      } = result;
      setTotalInfoData(total);
      setResourceInfoData({ ...resource });
      setWorkerStartDate(dayjs(workerStartTime));
      return true;
    }
    errorToastMessage(error, message);
    return false;
  }, [did]);

  /**
   * 검색된 그래프
   * @param {
   *  'CPU' |
   *  'RAM' |
   *  'GPU Core' |
   *  'GPU MEM' |
   *  'Call Count' |
   *  'Abnormal Process' |
   *  'Process Time' |
   *  'Response Time' |
   *  'Worker'
   * } type
   */
  const onSelectGraph = (type) => {
    let changed = {};
    if (type === 'CPU') {
      changed = {
        ...selectedGraph,
        type,
        cpu: !selectedGraph.cpu,
      };
    } else if (type === 'RAM') {
      changed = {
        ...selectedGraph,
        type,
        ram: !selectedGraph.ram,
      };
    } else if (type === 'GPU Core') {
      changed = {
        ...selectedGraph,
        type,
        gpuCore: !selectedGraph.gpuCore,
      };
    } else if (type === 'GPU MEM') {
      changed = {
        ...selectedGraph,
        type,
        gpuMem: !selectedGraph.gpuMem,
      };
    } else if (type === 'Call Count') {
      changed = {
        ...selectedGraph,
        type,
        callCnt: !selectedGraph.callCnt,
      };
    } else if (type === 'Abnormal Process') {
      changed = {
        ...selectedGraph,
        type,
        abProcess: !selectedGraph.abProcess,
      };
    } else if (type === 'Process Time') {
      changed = {
        ...selectedGraph,
        type,
        processTime: !selectedGraph.processTime,
      };
    } else if (type === 'Response Time') {
      changed = {
        ...selectedGraph,
        type,
        response: !selectedGraph.response,
      };
    } else if (type === 'Worker') {
      changed = {
        ...selectedGraph,
        type,
        worker: !selectedGraph.worker,
      };
    }
    setSelectedGraph(changed);
  };

  /**
   * history graph 데이터 요청
   * @param {string | undefined} start
   * @param {string | undefined} end
   */
  const requestHistoryGraphData = useCallback(
    async (sType) => {
      setLoading(true);
      const isLive = sType === 'live';
      let startTime = getUTCTime(
        dayjs(startDate).format(`${DATE_FORM} 00:00:00`),
      );
      let endTime = getUTCTime(dayjs(endDate).format(`${DATE_FORM} 23:59:59`));
      let interval = resolution.value;
      let searchType = 'range';

      if (isLive) {
        startTime = getUTCTime(
          dayjs().subtract(3, 'minutes').format(DATE_TIME_FORM),
        );
        endTime = getUTCTime(dayjs().format(DATE_TIME_FORM));
        interval = 1;
        searchType = 'live';
      }
      const selectedWorkerList = workerList
        .filter(({ value, checked }) => value !== 'all' && checked)
        .map(({ value }) => value)
        .join(',');

      let query = `deployment_id=${did}&start_time=${startTime}&end_time=${endTime}&interval=${interval}&search_type=${searchType}`;
      if (selectedWorkerList.length > 0) {
        query = `${query}&worker_list=${selectedWorkerList}`;
      }

      const res = await callApi({
        url: `deployments/dashboard_history?${query}`,
        method: 'get',
      });
      const { result, status, message, error } = res;
      setLoading(false);

      if (status === STATUS_SUCCESS) {
        const graphResult = result.graph_result?.map((d) => {
          const newData = { ...d };
          const { gpu_resource: gpuResources } = d;
          const gpuRes = gpuResources[0];
          newData.average_util_gpu = gpuRes ? gpuRes.average_util_gpu : 0;
          return newData;
        });
        setChartData(graphResult);
        setHistoryGraphData(result.graph_result);
        setSearchResultInfoData(result.total_info);
        setStatusCodeData(result.code_list);
        setErrorRecordData(result.error_log_list);
        return true;
      }
      errorToastMessage(error, message);
      return false;
    },
    [did, endDate, resolution.value, startDate, workerList],
  );

  /**
   * 검색 타입 선택 이벤트 핸들러
   * @param {string} type 검색 타입 range | live
   */
  const onChangeSearchType = (type) => {
    // end 시간은 현재시간, start 시간은 3분전 고정으로 요청
    setSearchType(type.value);
    if (type.value === 'range') {
      requestHistoryGraphData();
    }
  };

  const getData = useCallback(async () => {
    const infoData = await getInfoData();
    if (searchType === 'live') {
      const chartData = await requestHistoryGraphData(searchType);
      return infoData && chartData;
    }
    return infoData;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getInfoData, searchType]);

  /**
   * 처리시간 선택
   * @param {{label: string, value: number}} type
   */
  const onSelectProcessTime = (type) => {
    const { addData, value } = type;
    setSelectedGraphPer({
      ...selectedGraphPer,
      processTime: {
        value,
        selected: addData.value,
      },
    });
  };

  /**
   * Action 브래드크럼
   * @param {String} deploymentName
   */
  const breadCrumbHandler = (deploymentName) => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Serving',
            path: `/user/workspace/${wid}/deployments`,
            t,
          },
        },
        {
          component: {
            name: 'Deployment',
            path: `/user/workspace/${wid}/deployments`,
            t,
          },
        },
        {
          component: {
            name: deploymentName,
          },
        },
        {
          component: {
            name: 'Dashboard',
            t,
          },
        },
      ]),
    );
  };

  /**
   * 응답시간 선택
   * @param {{
   *  label: string,
   *  value: number,
   *  addData: { value: string}
   * }} type
   */
  const onSelectResponseType = (type) => {
    const { addData, value } = type;
    setSelectedGraphPer({
      ...selectedGraphPer,
      responseTime: {
        value,
        selected: addData.value,
      },
    });
  };

  const getDeploymentName = async () => {
    const response = await callApi({
      url: `deployments/deployment_name?deployment_id=${did}`,
      method: 'GET',
    });
    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      setTitle(result);
      breadCrumbHandler(result);
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  useEffect(() => {
    getDeploymentName();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * 최초 워커 시작시간에 따라 startDate, minDate 설정
   */
  useEffect(() => {
    const mDate = dayjs(workerStartDate).format(DATE_FORM);
    if (mount === false) {
      setMount(true);
      if (TODAY.diff(mDate, 'days') > 30) {
        // 30일 이상
        setStartDate(dayjs().subtract(30, 'days').format(DATE_FORM));
      } else {
        setStartDate(mDate);
      }
    }
    setMinDate(mDate);
  }, [mount, workerStartDate]);

  useEffect(() => {
    if (workerStartDate !== prevWorkerStartDate) {
      setPrevWorkerStartDate(workerStartDate);
    }
  }, [prevWorkerStartDate, workerStartDate, searchType]);

  useEffect(() => {
    requestHistoryGraphData();
  }, [requestHistoryGraphData]);

  useEffect(() => {
    onChangeDate(minDate, TODAY);
    requestHistoryGraphData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minDate]);

  useIntervalCall(getData, 1000);

  return (
    <DeployDashboardContent
      title={title}
      totalInfoData={totalInfoData}
      resourceInfoData={resourceInfoData}
      searchType={searchType}
      startDate={startDate}
      endDate={endDate}
      minDate={minDate}
      loading={loading}
      historyGraphData={historyGraphData}
      selectedGraphPer={selectedGraphPer}
      processTimeResponseTimeList={processTimeResponseTimeList}
      onSelectProcessTime={onSelectProcessTime}
      onSelectResponseType={onSelectResponseType}
      onSelectGraph={onSelectGraph}
      selectedGraph={selectedGraph}
      onChangeDate={onChangeDate}
      resolution={resolution}
      resolutionList={resolutionList}
      onChangeResolution={onChangeResolution}
      workers={workers}
      workerList={workerList}
      onChangeWorker={onChangeWorker}
      requestHistoryGraphData={requestHistoryGraphData}
      infoData={searchResultInfoData}
      chartData={chartData}
      logDownOptions={logDownOptions}
      logDownOptionsHandler={logDownOptionsHandler}
      onDownloadCallLogs={onDownloadCallLogs}
      statusCodeData={statusCodeData}
      errorRecordData={errorRecordData}
      onChangeSearchType={onChangeSearchType}
      onDownloadErrorRecord={onDownloadErrorRecord}
    />
  );
}

export default DeployDashboardPage;
