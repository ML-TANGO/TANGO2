import { useLayoutEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { Checkbox } from '@tango/ui-react';

import * as echarts from 'echarts';
import PropTypes from 'prop-types';

import classNames from 'classnames/bind';
import style from './DynamicCharts.module.scss';

const cx = classNames.bind(style);

const truncateText = (text) => {
  if (text.length > 24) {
    return `${text.slice(0, 24)}...`;
  }
  return text;
};

const getChartOptions = (type, data, column) => {
  if (type === 'bar') {
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross', // 'cross' | 'shadow' | 'line'
          crossStyle: {
            color: '#999',
          },
        },
      },
      grid: {
        top: 24,
        right: 24,
        bottom: 24,
        left: 24,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: data.x,
        boundaryGap: true, // bar 그래프는 boundaryGap 필요
      },
      yAxis: {
        type: 'value',
      },
      series: [
        {
          type: 'bar', // 그래프 타입
          data: data.y.map((value, index) => ({
            value,
            itemStyle: {
              color: [
                '#002F77',
                '#164ABE',
                '#2D76F8',
                '#93BAFF',
                '#C8DBFD',
                '#D9D9D9',
              ][index % 6], // 색상 배열 반복 적용
              borderRadius: [8, 8, 0, 0],
            },
          })),
          barWidth: '30%', // 막대 너비 설정
        },
      ],
      dataZoom: [
        // {
        //   type: 'slider', // 차트 아래(또는 오른쪽)에 슬라이더 UI
        //   show: true,
        //   realtime: true, // 드래그 시 즉시 차트 업데이트
        //   start: 0, // 초기에 보여줄 영역 시작(%)
        //   end: 100, // 초기에 보여줄 영역 끝(%)
        // },
        {
          type: 'inside', // 차트 영역 안에서 휠 스크롤, 드래그로 확대/축소
          // zoomOnMouseWheel: 'shift', // shift+휠 로 제한
          // moveOnMouseMove: 'alt',    // alt+드래그로 이동
        },
      ],
    };
  }

  if (type === 'line') {
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross', // 'cross' | 'shadow' | 'line'
          crossStyle: {
            color: '#999',
          },
        },
      },
      grid: {
        top: 24,
        right: 24,
        bottom: 24,
        left: 24,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: data.x, // X축 데이터
        boundaryGap: type === 'bar', // bar 차트는 boundaryGap 필요
      },
      yAxis: {
        type: 'value',
      },
      series: [
        {
          type: type, // 그래프 타입 (line 또는 bar)
          data: data.y, // Y축 데이터
          smooth: type === 'line', // line 차트에서는 smooth 적용
          lineStyle: { width: 2 },
          itemStyle: { color: '#002f77' },
          // areaStyle: type === 'line' ? { opacity: 0.1 } : undefined,
        },
      ],
      dataZoom: [
        // {
        //   type: 'slider', // 차트 아래(또는 오른쪽)에 슬라이더 UI
        //   show: true,
        //   realtime: true, // 드래그 시 즉시 차트 업데이트
        //   start: 0, // 초기에 보여줄 영역 시작(%)
        //   end: 100, // 초기에 보여줄 영역 끝(%)
        // },
        {
          type: 'inside', // 차트 영역 안에서 휠 스크롤, 드래그로 확대/축소
          // zoomOnMouseWheel: 'shift', // shift+휠 로 제한
          // moveOnMouseMove: 'alt',    // alt+드래그로 이동
        },
      ],
    };
  }
  if (type === 'pie') {
    // Pie 차트
    return {
      tooltip: {
        trigger: 'item', // 호버 시 정보 표시
      },
      legend: {
        orient: 'vertical', // 범례 세로 정렬
        right: '1px', // 오른쪽에 48px 여백
        top: 'center', // 중앙 정렬
        itemWidth: 14, // 범례 아이콘 크기
        itemHeight: 14,
        icon: 'circle',
        textStyle: {
          fontSize: 12,
        },
      },
      series: [
        {
          type: 'pie',
          radius: ['50%', '60%'], // 도넛 형태 (안쪽 반지름, 바깥쪽 반지름)
          center: ['140px', '50%'], // 그래프 위치 조정 (가로 140px → 280px 기준)
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4, // 둥근 모서리
          },

          label: {
            show: true,
            position: 'center', // 텍스트 가운데 정렬
            formatter: truncateText(column ?? '-'), // 가운데 글씨 삽입 아직 정해진게없음
            fontSize: 16,
            fontWeight: 'bold',
          },
          color: [
            '#002F77',
            '#164ABE',
            '#2D76F8',
            '#93BAFF',
            '#C8DBFD',
            '#D9D9D9',
          ],
          data: data.y.map((value, index) => ({
            value, // y값이 조각의 크기로 사용 되고, x값이 조각의 이름으로 사용 될 거다~
            name: `${data.x[index]}`, // 범례에 표시될 내용
          })),
        },
      ],
    };
  }

  // 기본 설정 반환 (예외 상황 대비)
  return {};
};

const DynamicCharts = ({
  type,
  data,
  title,
  id,
  column,
  checkboxHandler,
  checkedId,
  showInfoHandler,
}) => {
  const chartRef = useRef(null);
  const { t } = useTranslation();

  useLayoutEffect(() => {
    // if (data && data.steps && data.values) {
    //   const chartContainer = chartRef.current;

    //   if (chartContainer) {
    //     // 차트 초기화
    //     const chart = echarts.init(chartContainer);

    //     const options = getChartOptions(type, data); // 그래프 타입에 따라 옵션 생성
    //     chart.setOption(options);
    //     const resizeObserver = new ResizeObserver(() => {
    //       chart.resize();
    //     });
    //     resizeObserver.observe(chartContainer);

    //     return () => {
    //       chart.dispose();
    //       resizeObserver.disconnect();
    //     };
    //   }
    // }
    if (data && Array.isArray(data.x) && Array.isArray(data.y)) {
      // 수정: data.x, data.y
      const chartContainer = chartRef.current;

      if (chartContainer) {
        const chart = echarts.init(chartContainer);

        const options = getChartOptions(type, data, column);
        chart.setOption(options);
        const resizeObserver = new ResizeObserver(() => {
          chart.resize();
        });
        resizeObserver.observe(chartContainer);

        return () => {
          chart.dispose();
          resizeObserver.disconnect();
        };
      }
    } else {
      console.error('No Graph Data :', data);
    }
  }, [type, data, column]);

  return (
    <div className={cx('chart-item')}>
      <div className={cx('title')}>
        <Checkbox
          checked={checkedId.includes(id)}
          onChange={() => {
            checkboxHandler(id);
          }}
          customStyle={{
            padding: '0 0 0 16px',
            fontSize: '14px',
          }}
          // disabled={false}
        />
        <div className={cx('graph-name')}>{title}</div>
      </div>
      {data ? (
        <div
          className={cx('chart-container')}
          ref={chartRef}
          onClick={() => showInfoHandler(id)}
        ></div>
      ) : (
        <div
          className={cx('chart-container', 'creating')}
          onClick={() => showInfoHandler(id)}
        >
          {t('creatingGraph.message')}
        </div>
      )}

      {/* <div className={cx('epoch')}>
        <img src='/images/icon/info-icon.svg' alt='icon' />1 Epoch = {epoch}{' '}
        steps
      </div> */}
    </div>
  );
};

export default DynamicCharts;
