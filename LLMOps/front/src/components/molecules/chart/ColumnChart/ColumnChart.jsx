/* eslint-disable no-self-compare */
import { useEffect, useCallback } from 'react';
import * as am4core from '@amcharts/amcharts4/core';
import * as am4charts from '@amcharts/amcharts4/charts';
import am4themesAnimated from '@amcharts/amcharts4/themes/animated';

let chart;
const ColumnChart = ({ tagId, data = [], customStyle = {} }) => {
  /* 차트 포맷에 맞게 데이터 구조 변경 */
  function makeChartData(originData) {
    const chartData = [];

    originData.map((obj) => {
      const newObj = {};
      const name = Object.keys(obj)[0];
      const prob = Object.values(obj)[0];
      newObj.name = name;
      newObj.prob = prob;
      return chartData.push(newObj);
    });
    return chartData;
  }

  const generateChart = useCallback(() => {
    if (!document.getElementById(tagId) || data.length === 0) return;
    const chartData = makeChartData(data);

    // Themes
    am4core.useTheme(am4themesAnimated);

    chart = am4core.create(tagId, am4charts.XYChart);
    chart.scrollbarX = new am4core.Scrollbar();

    chart.paddingTop = 0;
    chart.paddingBottom = 0;
    chart.paddingRight = 20;
    chart.paddingLeft = 0;

    // Data
    chart.data = chartData;

    // Create axes
    const categoryAxis = chart.xAxes.push(new am4charts.CategoryAxis());
    categoryAxis.dataFields.category = 'name';
    categoryAxis.renderer.grid.template.location = 0;
    categoryAxis.renderer.minGridDistance = 30;
    categoryAxis.renderer.labels.template.horizontalCenter = 'right';
    categoryAxis.renderer.labels.template.verticalCenter = 'right';
    categoryAxis.renderer.labels.template.rotation = -45;
    categoryAxis.tooltip.disabled = true;
    categoryAxis.renderer.minHeight = 100;

    // 카테고리가 너무 많을 때 라벨이 지그재그로 두줄로 보이게 함
    // categoryAxis.renderer.labels.template.adapter.add('dy', (dy, target) => {
    //   // eslint-disable-next-line no-bitwise
    //   if (target.dataItem && target.dataItem.index & 2 === 2) {
    //     return dy + 25;
    //   }
    //   return dy;
    // });

    const valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
    valueAxis.renderer.minWidth = 30;

    // Create series
    const series = chart.series.push(new am4charts.ColumnSeries());
    series.sequencedInterpolation = true;
    series.dataFields.valueY = 'prob';
    series.dataFields.categoryX = 'name';
    series.tooltipText = '[{categoryX}: bold]{valueY}[/]';
    series.columns.template.strokeWidth = 0;

    series.tooltip.pointerOrientation = 'vertical';

    series.columns.template.column.cornerRadiusTopLeft = 10;
    series.columns.template.column.cornerRadiusTopRight = 10;
    series.columns.template.column.fillOpacity = 0.8;

    // on hover, make corner radiuses bigger
    const hoverState = series.columns.template.column.states.create('hover');
    hoverState.properties.cornerRadiusTopLeft = 0;
    hoverState.properties.cornerRadiusTopRight = 0;
    hoverState.properties.fillOpacity = 1;

    series.columns.template.adapter.add('fill', (_fill, target) => {
      return chart.colors.getIndex(target.dataItem.index);
    });

    // Cursor
    chart.cursor = new am4charts.XYCursor();
  }, [data, tagId]);

  useEffect(() => {
    if (data.length > 0) {
      generateChart();
    }
    return () => {
      if (chart) chart.dispose();
    };
  }, [generateChart, data]);
  return <div id={tagId} style={customStyle}></div>;
};

export default ColumnChart;
