import { useEffect, useState } from 'react';
import Chart from 'react-apexcharts';
// i18n
import { withTranslation } from 'react-i18next';

// Components
import EmptyBox from '@src/components/molecules/EmptyBox';

// Utils
import { capitalizeFirstLetter } from '@src/utils';

// CSS module
import './AccuracyLossChart.scss';

const colorSet = ['#0e4bff', '#e5261c', '#00e451', '#595a5b', '#ffad3b'];

/**  기본 차트 옵션
 *   !colors 명시되어있지 않은 컬러의 경우 그래프에서 색상이 회색으로 나올 수 있음. (추후 수정 필요)
 */
const chartDftOptions = {
  chart: {
    id: 'accuracy-loss-chart',
    toolbar: {
      // show: false,
      offsetX: -20,
    },
  },
  grid: {
    padding: {
      bottom: 15,
    },
  },
  stroke: {
    curve: 'straight',
    width: 2,
  },
  colors: colorSet,
  markers: {
    size: 0,
  },
  tooltip: {
    shared: true,
    intersect: false,
    y: {
      formatter: (y) => y,
    },
  },
};

/**
 * Chart에서 사용할 labels, yaxis 옵션을 data를 이용해 만들어 반환합니다.
 * @param {object} data metricsData
 * @param {object} info metricsInfo
 * @param {number} width chart width
 * @param {number} height chart height
 * @returns {object} {labels, yaxis}
 */
const makeChartOption = (data, info, width, height) => {
  if (Object.keys(info).length === 0) return {};

  const options = {};
  const {
    key_order: dataKeys,
    x,
    xaxisType = 'numeric',
    yaxisToFixed = 4,
  } = info;
  options.yaxis = dataKeys.map((dataKey, i) => {
    const min = Math.min(...data[dataKey]);
    const max = Math.max(...data[dataKey]);
    const yaxis = {
      opposite: i % 2 === 1, // 짝 수 번째 데이터 값에 대한 label은 반대로 나옵니다.
      title: {
        text: '',
      },
      labels: {
        formatter: (v) => v.toFixed(yaxisToFixed),
        style: {
          colors: colorSet[i],
        },
      },
    };
    if (min === max) {
      yaxis.min = min - 1;
      yaxis.max = max + 1;
    } else {
      yaxis.min = min;
      yaxis.max = max;
    }
    return yaxis;
  });

  const { label } = x;
  options.labels = [...x.value];

  if (label) {
    const subtitle = capitalizeFirstLetter(label);
    options.subtitle = {
      text: subtitle,
      offsetX: width / 2 - subtitle.length * 4,
      offsetY: height - 40,
    };
  }
  options.xaxis = {
    type: xaxisType,
    tickAmount: options.labels.length < 10 ? options.labels.length - 1 : 10,
    convertedCatToNumeric: false,
  };
  options.legend = {
    offsetY: -height + 30,
    markers: {
      width: 6,
      height: 6,
    },
  };

  return options;
};

/**
 * Chart에서 사용할 series를 data를 이용해 만들어 반환합니다.
 * @param {object} data metricsData
 * @param {object} info metricsInfo
 * @returns {Array} [{name, type, data}...]
 */
const makeSeries = (data, info) => {
  const { key_order: keyOrder } = info;
  if (keyOrder === undefined) return null;

  const series = keyOrder.map((dataKey) => {
    return {
      name: capitalizeFirstLetter(dataKey),
      type: 'line',
      data: [...data[dataKey]],
    };
  });

  return series;
};

const AccuracyLossChart = ({
  data,
  info,
  width,
  height,
  initEmptyMsg = 'noGraphData.message',
  // t,
}) => {
  const [chartOptions, setChartOptions] = useState(chartDftOptions);
  const [series, setSeries] = useState(null);
  useEffect(() => {
    const newSeries = makeSeries(data, info);
    if (!newSeries) return;
    setSeries(newSeries);
  }, [data, info]);

  useEffect(() => {
    setChartOptions({
      ...chartOptions,
      ...makeChartOption(data, info, width, height),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, info, width]);

  const { key_order: keyOrder } = info;

  if (!keyOrder || keyOrder.length <= 0) {
    return (
      <EmptyBox
        customStyle={{ height: '120px' }}
        text={initEmptyMsg}
        isBox
        isRed={true}
      />
    );
  }
  if (keyOrder.length <= 0 || data[keyOrder[0]].length < 1) {
    return (
      <EmptyBox
        customStyle={{ height: '120px' }}
        text={'noGraphData.message'}
        isBox
        isRed={true}
      />
    );
  }
  return (
    <div id='chart' className='AccuracyLossChart'>
      {series && (
        <Chart
          options={chartOptions}
          series={series || [{}]}
          type='line'
          width={width}
          height={height}
        />
      )}
    </div>
  );
};

export default withTranslation()(AccuracyLossChart);
