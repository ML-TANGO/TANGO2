import * as am4charts from '@amcharts/amcharts4/charts';
import * as am4core from '@amcharts/amcharts4/core';
import am4themesAnimated from '@amcharts/amcharts4/themes/animated';
import { useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

// Components
import EmptyBox from '@src/components/molecules/EmptyBox';

am4core.useTheme(am4themesAnimated);
const KR_TIME_DIFF = 9 * 60 * 60 * 1000;

let chart;
const TimeSeriesChart = ({ tagId, customStyle = {}, maxValue, totalUsage }) => {
  const { t } = useTranslation();

  const generateChart = useCallback(
    (dataSets) => {
      if (!document.getElementById(tagId) || dataSets.length === 0) return;
      chart = am4core.create(tagId, am4charts.XYChart);

      for (const data of dataSets) {
        for (const element of data) {
          const dateTime = new Date(element.date);
          const krDateTime = new Date(dateTime.getTime() + KR_TIME_DIFF);
          element.date = krDateTime;
        }
      }

      // chart.data = dataSets[0].reverse();

      const DateAxis = chart.xAxes.push(new am4charts.DateAxis());
      DateAxis.renderer.grid.template.location = 0;
      DateAxis.renderer.ticks.template.disabled = true;
      DateAxis.renderer.line.opacity = 0;
      DateAxis.renderer.grid.template.disabled = true;
      DateAxis.startLocation = 0.4;
      DateAxis.endLocation = 0.6;
      DateAxis.fontSize = '12px';
      DateAxis.dateFormats.setKey('minute', 'YYYY-MM-dd HH:mm');

      const valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
      valueAxis.tooltip.disabled = true;
      valueAxis.renderer.line.opacity = 0;
      valueAxis.renderer.ticks.template.disabled = true;
      valueAxis.min = -5;
      if (maxValue) valueAxis.max = maxValue + 5;
      valueAxis.strictMinMax = true;
      valueAxis.fontSize = '12px';

      const seriesColors = [
        '#FF7A00',
        '#FFEA53',
        '#3BABFF',
        '#7232FB',
        '#FF4EB8',
      ];
      const seriesDataFields = [
        {
          valueY: 'usage_gpu',
          data: dataSets[0],
          total: 'total_gpu',
          used: 'used_gpu',
          label: 'GPU',
        },
        {
          valueY: 'usage_cpu',
          data: dataSets[1],
          total: 'total_cpu',
          used: 'used_cpu',
          label: 'CPU',
        },
        {
          valueY: 'usage_ram',
          data: dataSets[2],
          total: 'total_ram',
          used: 'used_ram',
          label: 'RAM',
        },
        {
          valueY: 'usage_storage_data',
          data: dataSets[3],
          total: 'total_storage_data',
          used: 'used_storage_data',
          label: 'Data Storage',
        },
        {
          valueY: 'usage_storage_main',
          data: dataSets[4],
          total: 'total_storage_main',
          used: 'used_storage_main',
          label: 'Main Storage',
        },
      ];

      seriesDataFields.forEach((seriesField, index) => {
        const lineSeries = chart.series.push(new am4charts.LineSeries());
        lineSeries.dataFields.dateX = 'date';
        lineSeries.dataFields.valueY = seriesField.valueY;
        lineSeries.data = seriesField.data.reverse();
        lineSeries.name = seriesField.label;
        lineSeries.tooltipText = `{name} ${t('usage.label')}: [bold]{${
          seriesField.used
        }} / [bold]{${seriesField.total}} [bold]{valueY}%`;
        lineSeries.tooltip.getFillFromObject = false;
        lineSeries.tooltip.background.fill = am4core.color('#ffffff');
        lineSeries.tooltip.label.fill = am4core.color('#000');
        lineSeries.fill = am4core.color(seriesColors[index]);
        lineSeries.fillOpacity = 0;
        lineSeries.stroke = am4core.color(seriesColors[index]);
        lineSeries.strokeOpacity = 1;
        lineSeries.strokeWidth = 3;

        const bullet = lineSeries.bullets.push(new am4charts.CircleBullet());
        bullet.circle.radius = 0; // 0으로하면 동그라미 안보이고 선으로 보여줌
        bullet.circle.fill = am4core.color('#ffffff');
        bullet.circle.stroke = am4core.color(seriesColors[index]);
        bullet.circle.strokeWidth = 3;
      });

      chart.legend = new am4charts.Legend();
      chart.legend.position = 'bottom';
      chart.legend.labels.template.fontSize = '12px';
      chart.legend.itemContainers.template.events.on('hit', function (event) {
        const series = event.target.dataItem.dataContext;
        series.hidden = !series.hidden;
      });

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
    },
    [tagId, maxValue],
  );

  useEffect(() => {
    generateChart([
      totalUsage.gpu,
      totalUsage.cpu,
      totalUsage.ram,
      totalUsage.storage_data,
      totalUsage.storage_main,
    ]);
    return () => {
      if (chart) chart.dispose();
    };
  }, [generateChart, totalUsage]);

  return (
    <>
      {!totalUsage.gpu ? (
        <EmptyBox customStyle={customStyle} text={'noChartData.message'} />
      ) : (
        <div id={tagId} style={customStyle}></div>
      )}
    </>
  );
};

export default TimeSeriesChart;
