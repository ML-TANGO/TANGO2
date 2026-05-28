// Date Time Utils
import { useCallback, useEffect, useMemo, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import {
  DATE_FORM,
  DATE_TIME_FORM,
  getUTCTime,
  TODAY,
} from '@src/datetimeUtils';
import dayjs from 'dayjs';

import DeployWorkerMemoModalContent from '@src/components/Modal/DeployWorkerMemoModal/DeployWorkerMemoModalContent';
import DeployWorkerMemoModalFooter from '@src/components/Modal/DeployWorkerMemoModal/DeployWorkerMemoModalFooter';
import DeployWorkerMemoModalHeader from '@src/components/Modal/DeployWorkerMemoModal/DeployWorkerMemoModalHeader';
import DeployWorkerDashboardContent from '@src/components/pageContents/user/DeployWorkerDashboardContent';
// Components
import { toast } from '@src/components/Toast';

// Actions
import { openConfirm } from '@src/store/modules/confirm';
import { closeModal, openModal } from '@src/store/modules/modal';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';
import useLocalStorage from '@src/hooks/useLocalStorage';
// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function DeployWorkerDashboardPage() {
  const { t } = useTranslation();

  // Router Hooks
  const history = useHistory();
  const { id: wid, did, wkid } = useParams();

  // Redux Hooks
  const dispatch = useDispatch();

  const workerStatus = history.location?.state?.workerStatus || 'running';
  const title = history.location?.state?.title || '';

  // Costom hook
  const setWorkerStatusInLocalStorage = useLocalStorage(
    'worker_status',
    workerStatus,
  )[1];

  // Components State
  const [mount, setMount] = useState(false);
  const [totalInfoData, setTotalInfoData] = useState({
    deployment_run_time: 0,
    total_call_count: 0,
    total_success_rate: 0,
    total_log_size: 0,
    restart_count: 0,
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
  const [detailInfoOverview, setDetailInfoOverview] = useState(false);
  const [detailInfoData, setDetailInfoData] = useState({
    description: '',
    resource_info: {},
    version_info: {},
    version_info_changed: {},
  });
  const [searchResultInfoData, setSearchResultInfoData] = useState({});
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
  const [resolution, setResolution] = useState({
    label: 'Day',
    value: 60 * 60 * 24,
    isDisable: false,
  });
  // const [runningDays, setRunningDays] = useState(0);
  const [resourceGraphData, setResourceGraphData] = useState({
    memGraphData: {},
    cpuGraphData: {},
    gpuGraphData: [],
  });
  const [resolutionList, setResolutionList] = useState([
    { label: ['10', 'minute.label'], value: 60 * 10, disabled: false },
    { label: ['1', 'hour.label'], value: 60 * 60, disabled: false },
    { label: ['4', 'hour.label'], value: 60 * 60 * 4, disabled: false },
    { label: 'day.label', value: 60 * 60 * 24, disabled: false },
    { label: 'week.label', value: 60 * 60 * 24 * 7, disabled: false },
    { label: 'month.label', value: 60 * 60 * 24 * 30, disabled: false },
  ]);
  const [openStopModal, setOpenStopModal] = useState(false);
  const [systemLogLoading, setSystemLogLoading] = useState(false);
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
    worker: undefined,
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
   * 워커 삭제 요청 핸들러
   */
  const workerDeleteClickHandler = async () => {
    const response = await callApi({
      url: 'deployments/worker',
      method: 'delete',
      body: {
        deployment_worker_id_list: wkid,
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      // 삭제 했으니 워커 화면으로 이동
      defaultSuccessToastMessage('delete');
      history.push(`/user/workspace/${wid}/deployments/${did}/workers`);
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 삭제 모달 불러오는 함수
   */
  const openDeleteWorkerModal = () => {
    dispatch(
      openConfirm({
        title: 'deleteWorkerPopup.title.label',
        content: 'deleteWorker.title.message',
        submit: {
          text: 'delete.label',
          func: () => {
            workerDeleteClickHandler();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteWorker.message'),
        confirmMessage: t('deleteWorker.label'),
      }),
    );
  };

  /**
   * 단위 선택 핸들러
   * @param {string} value Resolution 값
   */
  const onChangeResolution = (value) => {
    setResolution(value);
  };

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
   *  'Response Time'
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
    }
    setSelectedGraph(changed);
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
        { label: ['10', 'minute.label'], value: 60 * 10, isDisable: false },
        { label: ['1', 'hour.label'], value: 60 * 60, isDisable: false },
        { label: ['4', 'hour.label'], value: 60 * 60 * 4, isDisable: false },
        { label: 'day.label', value: 60 * 60 * 24, isDisable: false },
        { label: 'week.label', value: 60 * 60 * 24 * 7, isDisable: false },
        { label: 'month.label', value: 60 * 60 * 24 * 30, isDisable: false },
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
        // disable: 10min
        disabledIndex = [0];
        defaultResolution = newResolutionList[1];
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
    },
    [changeResolutionListByRange],
  );

  /**
   * 검색 결과 데이터 받아오기 (검색 조건에 따라 차트/테이블 변경)
   */
  const requestHistoryGraphData = useCallback(
    async (sType) => {
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

      const query = `deployment_worker_id=${wkid}&start_time=${startTime}&end_time=${endTime}&interval=${interval}&search_type=${searchType}`;

      const res = await callApi({
        url: `deployments/dashboard_history?deployment_id=${did}&worker_list=${wkid}&${query}`,
        method: 'get',
      });

      const { result, status, message, error } = res;

      if (status === STATUS_SUCCESS) {
        const { graph_result, total_info, code_list, error_log_list } = result;
        setHistoryGraphData(graph_result);
        setSearchResultInfoData(total_info);
        setStatusCodeData(code_list);
        setErrorRecordData(error_log_list);
        return true;
      }
      errorToastMessage(error, message);
      return false;
    },
    [resolution.value, endDate, startDate, wkid, did],
  );

  /**
   * 검색 타입 선택 이벤트 핸들러
   * @param {string} type 검색 타입 range | live
   */
  const onChangeSearchType = (type) => {
    setSearchType(type.value);
    if (type.value === 'range') {
      requestHistoryGraphData();
    }
  };

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
    let query = `deployment_id=${did}&worker_list=${wkid}&start_time=${startTime}&end_time=${endTime}`;
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

    let query = `deployment_id=${did}&start_time=${startTime}&end_time=${endTime}&worker_list=${wkid}`;

    const response = await network.callApiWithPromise({
      url: `deployments/download_abnormal_record?${query}`,
      method: 'get',
    });
    const { status, data } = response;
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
   * worker 상태 호출
   */
  const getWorkerStatus = useCallback(async () => {
    const res = await callApi({
      url: `deployments/worker/dashboard_status?deployment_worker_id=${wkid}`,
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
  }, [wkid]);

  /**
   * Worker RAM, CPU, GPU 그래프 정보 호출
   */
  const requestResourceGraphData = useCallback(async () => {
    const res = await callApi({
      url: `deployments/worker/dashboard_resource_graph?deployment_worker_id=${wkid}`,
      method: 'get',
    });
    const { result, status, message, error } = res;
    if (status === STATUS_SUCCESS) {
      let memGraphData = {};
      let cpuGraphData = {};
      let gpuGraphData = [];
      const cpuHistory = result.cpu_history;
      const memHistory = result.mem_history;
      const gpuHistory = result.gpu_history;

      const cpuData = [];
      cpuHistory.forEach((cpu, idx) => {
        const { x, cpu_usage_on_pod } = cpu;
        cpuData[idx] = {
          x,
          y: cpu_usage_on_pod,
        };
      });
      cpuGraphData = {
        max: 100,
        cpuCores: `${result.cpu_cores.cpu_cores_total} | ${result.cpu_cores.cpu_cores_usage}%`,
        chartData: [
          {
            id: 'CPU 사용량',
            color: 'rgba(70, 41, 255, 0.8)',
            data: cpuData,
          },
        ],
      };

      // RAM 그래프 차트 data
      const memUsagePer = [];
      memHistory.forEach((mem, idx) => {
        const { x, mem_usage_per } = mem;
        memUsagePer[idx] = {
          x,
          y: mem_usage_per,
        };
      });
      memGraphData = {
        max: 100,
        ram: `${result.ram.ram_total} | ${result.ram.ram_usage}%`,
        chartData: [
          {
            id: '메모리 사용비율',
            color: 'rgba(33, 255, 77, 0.8)',
            data: memUsagePer,
          },
        ],
      };

      const gpuPer = Object.values(result.gpus);
      Object.keys(gpuHistory).forEach((gpus, i) => {
        const { utils_gpu, memory_used_ratio, memory_used, memory_total } =
          gpuPer[i];
        const gpuUtilData = [
          {
            id: 'GPU Util',
            color: 'rgba(0, 204, 204, 0.8)',
            data: [],
          },
          {
            id: 'Memory Util',
            color: 'rgba(0, 0, 255, 0.8)',
            data: [],
          },
        ];
        const gpuMemData = [
          {
            id: 'Memory Used',
            color: 'rgba(128, 128, 128, 0.8)',
            data: [],
          },
        ];
        gpuHistory[gpus].forEach((gpu, idx) => {
          const { x, memory_used, util_gpu, util_memory } = gpu;
          gpuUtilData[0].data[idx] = {
            x,
            y: util_gpu,
          };
          gpuUtilData[1].data[idx] = {
            x,
            y: util_memory,
          };
          gpuMemData[0].data[idx] = {
            x,
            y: memory_used,
          };
        });

        gpuGraphData[i] = {
          gpuUtil: utils_gpu,
          totalMemory: memory_total,
          usedMemory: memory_used,
          usedMemoryRatio: memory_used_ratio,
          gpuGraph: {
            max: 100,
            chartData: gpuUtilData,
          },
          memGraph: {
            max: memory_total,
            chartData: gpuMemData,
          },
        };
      });
      setResourceGraphData({
        memGraphData,
        cpuGraphData,
        gpuGraphData,
      });
      return true;
    }
    errorToastMessage(error, message);
    return false;
  }, [wkid]);

  /**
   * 워커 정보 펼치기/접기
   */
  const detailInfoOverviewHandler = async () => {
    setDetailInfoOverview(!detailInfoOverview);
    if (!detailInfoOverview) {
      getWorkerInfo();
    }
  };

  /**
   * 워커 정보
   */
  const getWorkerInfo = useCallback(async () => {
    const res = await callApi({
      url: `deployments/worker/dashboard_worker_info?deployment_worker_id=${wkid}`,
      method: 'get',
    });
    const { result, status, message, error } = res;
    if (status === STATUS_SUCCESS) {
      setDetailInfoData(result);
    } else {
      errorToastMessage(error, message);
    }
  }, [wkid]);

  /**
   * Worker list로 돌아가기
   */
  const gotoList = () => {
    history.push({
      pathname: `/user/workspace/${wid}/deployments/${did}/workers`,
      workerStatus,
    });
  };

  /**
   * Worker Memo 핸들러
   * @param {number} workerId
   * @param {number} prevMemo 이전 메모 내용
   */
  const workerMemoModalHandler = (workerId, prevMemo) => {
    const modalType = 'DEPLOY_WORKER_MEMO';
    dispatch(
      openModal({
        modalType,
        modalData: {
          headerRender: DeployWorkerMemoModalHeader,
          contentRender: DeployWorkerMemoModalContent,
          footerRender: DeployWorkerMemoModalFooter,
          workerId,
          prevMemo,
          submit: (memo) => {
            dispatch(closeModal(modalType));
          },
          memoEdit: (id, desc) => {
            workerMemoHandler(id, desc);
          },
        },
      }),
    );
  };

  /**
   *  Worker Memo 수정 요청 핸들러
   *  @param {number} workerId
   *  @param {string} desc 이전 메모 내용
   */
  const workerMemoHandler = async (workerId, desc) => {
    const response = await callApi({
      url: `deployments/worker/description`,
      method: 'put',
      body: {
        deployment_worker_id: workerId,
        description: desc,
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('update');
      getWorkerInfo();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Worker 중지 모달열기 설정
   */
  const workerStopHandler = (open) => {
    setOpenStopModal(open);
  };

  /**
   * Worker 중지 요청
   */
  const stopWorkerRequest = async () => {
    const response = await callApi({
      url: `deployments/worker/stop?deployment_worker_id=${wkid}`,
      method: 'get',
    });
    const { status, message, error } = response;
    if (status !== STATUS_SUCCESS) {
      errorToastMessage(error, message);
    }
  };

  /**
   * worker status get
   * worker history 그래프 데이터 get실행
   */
  const getWorkerData = useCallback(() => {
    const isSuccessGetStatus = getWorkerStatus();
    const isSuccessGetHistory = requestResourceGraphData();
    if (isSuccessGetStatus && isSuccessGetHistory) {
      if (searchType === 'live') {
        requestHistoryGraphData(searchType);
      }
      return true;
    }
    return false;
  }, [
    getWorkerStatus,
    requestHistoryGraphData,
    requestResourceGraphData,
    searchType,
  ]);

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

  /**
   * system log 모달
   */
  const onSystemLog = async (wid, systemData) => {
    const modalType = 'SYSTEM_LOG';
    // getSystemLogData(wid);

    dispatch(
      openModal({
        modalType,
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              dispatch(closeModal(modalType));
            },
          },
          deploymentWorkerId: wid,
          systemLogData: systemData,
          systemLogLoading,
        },
      }),
    );
  };

  /**
   * 시스템 로그 데이터 요청
   * @param {Number} wid deployment worker id
   */
  const getSystemLogData = async (wid) => {
    setSystemLogLoading(true);
    const response = await callApi({
      url: `deployments/worker/system_log/${wid}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      onSystemLog(wid, result); //* 모달 띄우기
    } else {
      errorToastMessage(error, message);
    }

    setSystemLogLoading(false);
  };

  useEffect(() => {
    loadModalComponent('DEPLOY_WORKER_MEMO');
    loadModalComponent('SYSTEM_LOG');
  }, []);

  /**
   * 최초 워커 시작시간에 따라 startDate, minDate 설정
   */
  useEffect(() => {
    const minDate = dayjs(workerStartDate);
    if (mount === false) {
      setMount(true);
      if (TODAY.diff(minDate, 'days') > 30) {
        // 30일 이상
        setStartDate(dayjs().subtract(30, 'days').format(DATE_FORM));
      } else {
        setStartDate(minDate.format(DATE_FORM));
      }
    }
    setMinDate(minDate.format(DATE_FORM));
  }, [workerStartDate, mount, minDate]);

  useEffect(() => {
    if (workerStartDate !== prevWorkerStartDate) {
      setPrevWorkerStartDate(workerStartDate);
      if (searchType === 'range') {
        requestHistoryGraphData();
      }
    }
  }, [
    prevWorkerStartDate,
    workerStartDate,
    requestHistoryGraphData,
    searchType,
  ]);

  useEffect(() => {
    getWorkerInfo();
  }, [getWorkerInfo]);

  useEffect(() => {
    onChangeDate(minDate, TODAY);
    requestHistoryGraphData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minDate]);

  useEffect(() => {
    setWorkerStatusInLocalStorage(workerStatus);
  }, [setWorkerStatusInLocalStorage, workerStatus]);

  useIntervalCall(getWorkerData, 1000);

  return (
    <DeployWorkerDashboardContent
      workerId={wkid}
      endDate={endDate}
      minDate={minDate}
      startDate={startDate}
      searchType={searchType}
      resolution={resolution}
      workerStatus={workerStatus}
      openStopModal={openStopModal}
      selectedGraph={selectedGraph}
      totalInfoData={totalInfoData}
      detailInfoData={detailInfoData}
      resolutionList={resolutionList}
      statusCodeData={statusCodeData}
      logDownOptions={logDownOptions}
      errorRecordData={errorRecordData}
      historyGraphData={historyGraphData}
      resourceInfoData={resourceInfoData}
      selectedGraphPer={selectedGraphPer}
      resourceGraphData={resourceGraphData}
      detailInfoOverview={detailInfoOverview}
      searchResultInfoData={searchResultInfoData}
      processTimeResponseTimeList={processTimeResponseTimeList}
      gotoList={gotoList}
      onChangeDate={onChangeDate}
      onSelectGraph={onSelectGraph}
      workerStopHandler={workerStopHandler}
      stopWorkerRequest={stopWorkerRequest}
      onChangeSearchType={onChangeSearchType}
      onChangeResolution={onChangeResolution}
      onDownloadCallLogs={onDownloadCallLogs}
      onSelectProcessTime={onSelectProcessTime}
      onSelectResponseType={onSelectResponseType}
      logDownOptionsHandler={logDownOptionsHandler}
      onDownloadErrorRecord={onDownloadErrorRecord}
      workerMemoModalHandler={workerMemoModalHandler}
      requestHistoryGraphData={requestHistoryGraphData}
      detailInfoOverviewHandler={detailInfoOverviewHandler}
      openDeleteWorkerModal={openDeleteWorkerModal}
      getSystemLogData={getSystemLogData}
      systemLogLoading={systemLogLoading}
      title={title}
    />
  );
}

export default DeployWorkerDashboardPage;
