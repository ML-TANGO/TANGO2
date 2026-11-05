import * as am4charts from '@amcharts/amcharts4/charts';
import * as am4core from '@amcharts/amcharts4/core';
import am4themesAnimated from '@amcharts/amcharts4/themes/animated';
import { useCallback, useEffect } from 'react';

// Components
import EmptyBox from '@src/components/molecules/EmptyBox';

am4core.useTheme(am4themesAnimated);

const createAxisAndSeries = (
  chart,
  dateX,
  valueY,
  name,
  opposite,
  tooltipText = 'valueY',
  maxValue,
  color,
  idx,
) => {
  const valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
  if (chart.yAxes.indexOf(valueAxis) !== 0) {
    valueAxis.syncWithAxis = chart.yAxes.getIndex(0);
  }

  const series = chart.series.push(new am4charts.LineSeries());
  series.dataFields.dateX = dateX;
  series.dataFields.valueY = valueY;
  series.dataFields.categoryX = 'x';
  series.strokeWidth = 2;
  if (color) series.stroke = am4core.color(color);
  series.yAxis = valueAxis;
  series.name = name;
  series.tooltip.fontSize = '12px';
  series.tooltipText = tooltipText;
  series.tooltip.getFillFromObject = false;
  series.tooltip.background.fill = am4core.color('#ffffff');
  series.tooltip.label.fill = am4core.color('#000');
  series.tensionX = 0.8;
  series.showOnInit = true;

  valueAxis.cursorTooltipEnabled = false;
  if (maxValue) valueAxis.max = maxValue;
  valueAxis.renderer.line.strokeOpacity = 1;
  valueAxis.renderer.line.strokeWidth = 2;
  valueAxis.renderer.line.stroke = series.stroke;
  valueAxis.renderer.grid.template.strokeWidth = 1;
  valueAxis.renderer.labels.template.fill = series.stroke;

  // ** 좌측 높이 한 개만 띄우기 [true : 띄우지 않기] **
  valueAxis.renderer.grid.template.disabled = true;
  valueAxis.renderer.labels.template.disabled = true;
  // ** 첫번째 값만 띄움 **
  if (idx === 0) {
    valueAxis.renderer.grid.template.disabled = false;
    valueAxis.renderer.labels.template.disabled = false;
  }

  // valueAxis.renderer.opposite = opposite;
  valueAxis.fontSize = '12px';
  // valueAxis.fontWeight = '500';
  const interfaceColors = new am4core.InterfaceColorSet();
  const bullet = series.bullets.push(new am4charts.CircleBullet());
  bullet.circle.stroke = interfaceColors.getFor('background');
  bullet.circle.strokeWidth = 2;
  bullet.circle.fill = am4core.color(color);
};

let chart;
const MultipleTimeSeriesChart = ({
  tagId,
  data = [],
  axisSeriesArr = [{ dateX: 'timestamp', valueY: 'usage' }],
  customStyle = {},
}) => {
  const generateChart = useCallback(() => {
    if (!document.getElementById(tagId) || data.length === 0) return;
    chart = am4core.create(tagId, am4charts.XYChart);
    chart.data = data;

    // Create axes
    const dateAxis = chart.xAxes.push(new am4charts.DateAxis());
    dateAxis.renderer.line.opacity = 0;
    dateAxis.renderer.grid.template.disabled = true;
    dateAxis.renderer.minGridDistance = 100;
    dateAxis.fontSize = '12px';
    dateAxis.dateFormats.setKey('minute', 'YYYY-MM-dd HH:mm');

    for (let i = 0; i < axisSeriesArr.length; i += 1) {
      const {
        dateX,
        valueY,
        maxValue,
        tooltipText,
        opposite,
        legendLabel,
        color,
      } = axisSeriesArr[i];
      createAxisAndSeries(
        chart,
        dateX,
        valueY,
        legendLabel,
        opposite,
        tooltipText,
        maxValue,
        color,
        i,
      );
    }

    // Add legend
    chart.legend = new am4charts.Legend();

    // Add cursor
    chart.cursor = new am4charts.XYCursor();

    const { zoomOutButton } = chart;
    zoomOutButton.align = 'right';
    zoomOutButton.valign = 'bottom';
    zoomOutButton.marginBottom = 11;
    zoomOutButton.width = 32;
    zoomOutButton.height = 32;
    zoomOutButton.background.cornerRadius(4, 4, 4, 4);
    zoomOutButton.background.fill = am4core.color('#f0f0f0');
    zoomOutButton.icon.stroke = am4core.color('#747474');
    zoomOutButton.icon.strokeWidth = 2;
    zoomOutButton.icon.align = 'center';
    zoomOutButton.icon.valign = 'middle';
    zoomOutButton.background.states.getKey('hover').properties.fill =
      am4core.color('#dbdbdb');

    chart.cursor = new am4charts.XYCursor();
    chart.cursor.behavior = 'panX';
    chart.cursor.lineX.opacity = 0;
    chart.cursor.lineY.opacity = 0;

    chart.scrollbarX = new am4core.Scrollbar();
    chart.scrollbarX.parent = chart.bottomAxesContainer;
    chart.scrollbarX.background.fill = am4core.color('#dbdbdb');
    chart.scrollbarX.thumb.background.fill = am4core.color('#2d76f8');
    chart.scrollbarX.thumb.background.states.getKey('hover').properties.fill =
      am4core.color('#2d76f8');
    chart.scrollbarX.thumb.height = 8;

    const markerTemplate = chart.legend.markers.template;
    markerTemplate.width = 12;
    markerTemplate.height = 12;
    const marker = chart.legend.markers.template.children.getIndex(0);
    marker.width = '12px';
    marker.height = '12px';
    marker.cornerRadius(3, 3, 3, 3);

    function customizeGrip(customGrip) {
      const grip = customGrip;
      grip.width = 20;
      grip.height = 20;
      grip.background.fill = am4core.color('#ffffff');
      grip.background.fillOpacity = 1;
      grip.background.states.getKey('hover').properties.fill =
        am4core.color('#ffffff');
      grip.icon.disabled = true;
      const shadow = new am4core.DropShadowFilter();
      shadow.dx = 1;
      shadow.dy = 2;
      shadow.blur = 6;
      shadow.color = am4core.color('rgba(0, 0, 0, 0.3)');
      grip.filters.push(shadow);
    }

    customizeGrip(chart.scrollbarX.startGrip);
    customizeGrip(chart.scrollbarX.endGrip);
  }, [data, tagId, axisSeriesArr]);

  useEffect(() => {
    generateChart();
    return () => {
      if (chart) chart.dispose();
    };
  }, [generateChart, data]);
  return (
    <>
      {data.length === 0 ? (
        <EmptyBox
          customStyle={{ height: 'calc(100% - 110px)' }}
          text={'noChartData.message'}
        />
      ) : (
        <div id={tagId} style={customStyle}></div>
      )}
    </>
  );
};

export default MultipleTimeSeriesChart;
