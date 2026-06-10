import { useEffect } from 'react';
import * as am4core from '@amcharts/amcharts4/core';
import * as am4charts from '@amcharts/amcharts4/charts';
// import am4themesAnimated from '@amcharts/amcharts4/themes/animated';

// Utils
import { capitalizeFirstLetter } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './AccuracyLossChart2.module.scss';
const cx = classNames.bind(style);

const colorSet = ['#0e4bff', '#e5261c', '#00e451', '#595a5b', '#ffad3b'];

// am4core.useTheme(am4themesAnimated);

const generateChartData = (data, info) => {
  const { key_order: keyOrder, x } = info;
  if (keyOrder === undefined) return null;

  const chartData = x.value.map((xValue, idx) => {
    const newData = { x: xValue };

    for (let i = 0; i < keyOrder.length; i += 1) {
      newData[keyOrder[i]] = data[keyOrder[i]][idx];
    }

    return newData;
  });

  return chartData;
};

const createAxisAndSeries = (chart, field, name, opposite) => {
  const valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
  if (chart.yAxes.indexOf(valueAxis) !== 0) {
    valueAxis.syncWithAxis = chart.yAxes.getIndex(0);
  }

  const series = chart.series.push(new am4charts.LineSeries());
  series.dataFields.valueY = field;
  series.dataFields.categoryX = 'x';
  series.strokeWidth = 2;
  series.yAxis = valueAxis;
  series.name = name;
  series.tooltip.fontSize = '12px';
  series.tooltipText = '{name}: [bold]{valueY}[/]';
  series.tensionX = 0.8;
  series.showOnInit = true;

  valueAxis.cursorTooltipEnabled = false;
  valueAxis.renderer.line.strokeOpacity = 1;
  valueAxis.renderer.line.strokeWidth = 2;
  valueAxis.renderer.line.stroke = series.stroke;
  valueAxis.renderer.grid.template.strokeWidth = 1;
  valueAxis.renderer.labels.template.fill = series.stroke;
  valueAxis.renderer.opposite = opposite;
  valueAxis.fontSize = '12px';
  valueAxis.fontWeight = '500';
};

let isFirst = true;
let chart;
const AccuracyLossChart = ({ data, info, width, height }) => {
  useEffect(() => {
    if (data.length === 0 || Object.keys(info).length === 0) return;
    if (!isFirst) {
      // chart.data = generateChartData(data, info);
      chart.data = [];
      chart.addData(generateChartData(data, info));
      return;
    }
    isFirst = false;
    chart = am4core.create('chartdiv', am4charts.XYChart);

    chart.paddingTop = 0;
    chart.paddingBottom = 0;
    chart.paddingRight = 0;
    chart.paddingLeft = 0;
    chart.data = generateChartData(data, info);
    chart.colors.list = colorSet.map((color) => am4core.color(color));

    const xAxis = chart.xAxes.push(new am4charts.CategoryAxis());
    xAxis.dataFields.category = 'x';
    xAxis.title.text = capitalizeFirstLetter(info.x.label || '');
    xAxis.fontSize = '12px';
    xAxis.fontWeight = '500';

    const { key_order: keyOrder } = info;
    for (let i = 0; i < keyOrder.length; i += 1) {
      createAxisAndSeries(
        chart,
        keyOrder[i],
        capitalizeFirstLetter(keyOrder[i]),
        i % 2 === 1,
      );
    }

    chart.legend = new am4charts.Legend();
    chart.legend.fontSize = '12px';
    chart.legend.position = 'top';
    chart.legend.marginBottom = '12px';
    chart.legend.useDefaultMarker = true;
    const markerTemplate = chart.legend.markers.template;
    markerTemplate.width = 6;
    markerTemplate.height = 6;
    const marker = chart.legend.markers.template.children.getIndex(0);
    marker.width = '6px';
    marker.height = '6px';
    marker.cornerRadius(3, 3, 3, 3);
    chart.cursor = new am4charts.XYCursor();
  }, [data, info, isFirst]);
  useEffect(() => {
    return () => {
      isFirst = true;
    };
  }, []);

  const { key_order: keyOrder } = info;
  if (!keyOrder || keyOrder.length <= 0 || data[keyOrder[0]].length <= 1) {
    return <div className={cx('no-data')}>Not enough data.</div>;
  }

  return <div id='chartdiv' style={{ width, height }}></div>;
};

export default AccuracyLossChart;
