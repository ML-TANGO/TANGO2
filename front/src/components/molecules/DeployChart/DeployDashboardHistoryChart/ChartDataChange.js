// utils
import {
  convertTimeStamp,
  DATE_TIME_FORM,
  getUTC9Time,
} from '@src/datetimeUtils';

/**
 * chart에 입력할 데이터 폼으로 수정
 * @param {{
 *  time: number,
 *  nginx_count: number,
 *  error_count: number,
 *  [percent]_average_response_time: number,
 *  average_nginx_response_time: number,
 *  average_cpu_usage_on_pod: number,
 *  average_mem_usage_per: number,
 *  gpu_resource: number,
 *  worker_count: number,
 * }} data
 * @param {
 *  'ALL' |
 *  'CPU' |
 *  'RAM' |
 *  'GPU Core' |
 *  'GPU MEM' |
 *  'Call Count' |
 *  'Process Time' |
 *  'Response Time' |
 *  'Worker'
 * } selectedGraph
 * @param {{
 *  value: number,
 *  selected: string,
 * }} selectedGraphPer
 * 0: '중앙값', '1': 99번째 백분위, '2': 95번째 백분위, '3': 90번째 백분위 '4': 평균
 * @param {string} selectedAbnormal
 * @param {{
 *  nginx: true,
 *  api: true,
 * }} abnormalCheckOption
 * @param {translation} t
 * @returns {{
 *  optoins: {
 *    chart: {
 *      id: string,
 *    },
 *    xaxis: {
 *      categories: string[],
 *    },
 *    yaxis: {
 *      axisBorder: {
 *        show: boolean,
 *        color: string,
 *      },
 *      labels: {
 *        style: {
 *          color: string,
 *        },
 *      },
 *      title: {
 *        text: string,
 *        style: {
 *          color: string,
 *        },
 *      },
 *    }[]
 *  },
 *  series: {
 *    name: string,
 *    data: number[],
 *  }[],
 * }}
 */
export function reorganization(
  data,
  selectedGraph,
  selectedGraphPer,
  selectedAbnormal,
  abnormalCheckOption,
  t,
) {
  if (!data || !Array.isArray(data)) return;
  const {
    cpu: isCPUSelect,
    ram: isRAMSelect,
    gpuCore: isGPUCoreSelect,
    gpuMem: isGPUMemSelect,
    callCnt: isCallCntSelect,
    abProcess: isAbProcessSelect,
    processTime: isProcessTimeSelect,
    response: isResponseSelect,
    worker: isWorkerSelect,
  } = selectedGraph;

  const { processTime: processTimePer, responseTime: responseTimePer } =
    selectedGraphPer;
  let abnormal = '';
  if (selectedAbnormal === 'count') {
    if (
      abnormalCheckOption.nginx === true &&
      abnormalCheckOption.api === true
    ) {
      abnormal = 'error_count';
    } else if (
      abnormalCheckOption.nginx === true &&
      abnormalCheckOption.api === false
    ) {
      abnormal = 'nginx_error_count';
    } else if (
      abnormalCheckOption.nginx === false &&
      abnormalCheckOption.api === true
    ) {
      abnormal = 'monitor_error_count';
    }
  } else if (selectedAbnormal === 'rate') {
    if (
      abnormalCheckOption.nginx === true &&
      abnormalCheckOption.api === true
    ) {
      abnormal = 'error_rate';
    } else if (
      abnormalCheckOption.nginx === true &&
      abnormalCheckOption.api === false
    ) {
      abnormal = 'nginx_error_rate';
    } else if (
      abnormalCheckOption.nginx === false &&
      abnormalCheckOption.api === true
    ) {
      abnormal = 'monitor_error_rate';
    }
  }

  const series = {
    left: [],
    right: [],
  };
  const leftAxis = {
    unitsPerTick: 1,
    tickSize: 10,
    color: '#000',
    min: 0,
    max: 5,
    name: `${t('left.label')} ${t('axis.label')} ${t('data.label')}`,
  };
  const rightAxis = {
    unitsPerTick: 1,
    tickSize: 10,
    color: '#000',
    min: 0,
    max: 5,
    name: `${t('right.label')} ${t('axis.label')} ${t('data.label')}`,
  };
  let axis = {
    bottom: {
      name: 'Date time',
      unitsPerTick: 1,
      tickSize: 10,
      color: '#000',
      data: [],
      max: data.length - 1,
      min: 0,
    },
  };

  const callCntSeries = {
    name: t('callCount.label'),
    color: '#3232FF',
    lineWidth: 3,
    series: [],
  };
  const abProcessSeries = {
    name: t('abnormalProcessing.label'),
    color: '#FF0000',
    lineWidth: 3,
    series: [],
  };
  const processTimeSeries = {
    name: t('processingTime.label'),
    color: '#369F36',
    lineWidth: 3,
    series: [],
  };
  const responseTimeSeries = {
    name: t('responseTime.label'),
    color: '#46B4B4',
    lineWidth: 3,
    series: [],
  };
  const cpuSeries = {
    name: 'CPU',
    color: '#FFCD28',
    lineWidth: 3,
    series: [],
  };
  const ramSeries = {
    name: 'RAM',
    color: '#FFAA28',
    lineWidth: 3,
    series: [],
  };
  const gpuCoreSeries = {
    name: 'GPU Core',
    color: '#FF7F50',
    lineWidth: 3,
    series: [],
  };
  const gpuMemSeries = {
    name: 'GPU MEM',
    color: '#957745',
    lineWidth: 3,
    series: [],
  };
  const workerSeries = {
    name: t('worker.label'),
    color: '#AD19EC',
    lineWidth: 3,
    series: [],
  };

  for (let i = 0; i < data.length; i++) {
    const {
      time,
      nginx_count: count, //콜수
      [abnormal]: abProcessing, // 비정상처리
      [`${processTimePer.selected}_processing_time`]: procTime, // 처리시간
      [`${responseTimePer.selected}_response_time`]: response, // 응답시간
      average_cpu_usage_on_pod: cpu, // CPU
      average_mem_usage_per: ram, // RAM
      gpu_resource,
      worker_count,
    } = data[i];

    axis.bottom.data = [
      ...axis.bottom.data,
      getUTC9Time(convertTimeStamp(time, DATE_TIME_FORM)),
    ];

    // 왼쪽 y축
    if (isCallCntSelect) {
      if (axis.left === undefined) {
        axis.left = leftAxis;
      }
      axis.left.max = Math.max(axis.left.max, count);
      callCntSeries.series = [...callCntSeries.series, count];
    }
    if (isAbProcessSelect && abProcessing !== undefined) {
      if (axis.left === undefined) {
        axis.left = leftAxis;
      }
      axis.left.max = Math.max(axis.left.max, abProcessing);
      abProcessSeries.series = [...abProcessSeries.series, abProcessing];
    }
    if (isProcessTimeSelect) {
      if (axis.left === undefined) {
        axis.left = leftAxis;
      }
      axis.left.max = Math.max(axis.left.max, procTime);
      processTimeSeries.series = [...processTimeSeries.series, procTime];
    }
    if (isResponseSelect) {
      if (axis.left === undefined) {
        axis.left = leftAxis;
      }
      axis.left.max = Math.max(axis.left.max, response);
      responseTimeSeries.series = [...responseTimeSeries.series, response];
    }
    // 오른쪽 y축
    if (isCPUSelect) {
      if (axis.right === undefined) {
        axis.right = rightAxis;
      }
      axis.right.max = Math.max(axis.right.max, cpu);
      cpuSeries.series = [...cpuSeries.series, cpu];
    }
    if (isRAMSelect) {
      if (axis.right === undefined) {
        axis.right = rightAxis;
      }
      axis.right.max = Math.max(axis.right.max, ram);
      ramSeries.series = [...ramSeries.series, ram];
    }
    if (isGPUCoreSelect) {
      if (axis.right === undefined) {
        axis.right = rightAxis;
      }
      let gpuCore = 0;
      if (gpu_resource.length > 0) {
        gpuCore = gpu_resource['0']['average_util_gpu'];
      }
      axis.right.max = Math.max(axis.right.max, gpuCore);
      gpuCoreSeries.series = [...gpuCoreSeries.series, gpuCore];
    }
    if (isGPUMemSelect) {
      if (axis.right === undefined) {
        axis.right = rightAxis;
      }
      let gpuMem = 0;
      if (gpu_resource.length > 0) {
        gpuMem = gpu_resource['0']['average_gpu_memory_used_per'];
      }
      axis.right.max = Math.max(axis.right.max, gpuMem);
      gpuMemSeries.series = [...gpuMemSeries.series, gpuMem];
    }
    if (isWorkerSelect) {
      if (axis.right === undefined) {
        axis.right = rightAxis;
      }
      axis.right.max = Math.max(axis.right.max, worker_count);
      workerSeries.series = [...workerSeries.series, worker_count];
    }
  }

  // 왼쪽 y축
  if (isCallCntSelect) {
    if (series.left === undefined) {
      series.left = [];
    }
    series.left = [...series.left, callCntSeries];
  }
  if (isAbProcessSelect) {
    if (series.left === undefined) {
      series.left = [];
    }
    series.left = [...series.left, abProcessSeries];
  }
  if (isProcessTimeSelect) {
    if (series.left === undefined) {
      series.left = [];
    }
    series.left = [...series.left, processTimeSeries];
  }
  if (isResponseSelect) {
    if (series.left === undefined) {
      series.left = [];
    }
    series.left = [...series.left, responseTimeSeries];
  }

  // 오른쪽 y축
  if (isCPUSelect) {
    if (series.right === undefined) {
      series.right = [];
    }
    series.right = [...series.right, cpuSeries];
  }
  if (isRAMSelect) {
    if (series.right === undefined) {
      series.right = [];
    }
    series.right = [...series.right, ramSeries];
  }
  if (isGPUCoreSelect) {
    if (series.right === undefined) {
      series.right = [];
    }
    series.right = [...series.right, gpuCoreSeries];
  }
  if (isGPUMemSelect) {
    if (series.right === undefined) {
      series.right = [];
    }
    series.right = [...series.right, gpuMemSeries];
  }
  if (isWorkerSelect) {
    if (series.right === undefined) {
      series.right = [];
    }
    series.right = [...series.right, workerSeries];
  }

  if (leftAxis.max > 30) {
    leftAxis.unitsPerTick = Math.floor(leftAxis.max / 30);
  }
  if (rightAxis.max > 30) {
    rightAxis.unitsPerTick = Math.floor(rightAxis.max / 30);
  }

  if (axis.left === undefined) {
    axis.left = leftAxis;
  }
  if (axis.right === undefined) {
    axis.right = rightAxis;
  }

  return {
    series,
    axis,
  };
}
