import { useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import * as am4charts from '@amcharts/amcharts4/charts';
import * as am4core from '@amcharts/amcharts4/core';
import am4themesAnimated from '@amcharts/amcharts4/themes/animated';

// Components
import EmptyBox from '@src/components/molecules/EmptyBox';

am4core.useTheme(am4themesAnimated);
const KR_TIME_DIFF = 9 * 60 * 60 * 1000;

let chart;

const WorkSpaceResourceChart = ({
  tagId,
  customStyle = {},
  maxValue,
  totalUsage,
}) => {
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

      // 그래프가 안그려지면 시간이 오름차순 내림차순 확인해서 활성화 비활성화 해주면된다.
      chart.data = dataSets[0].reverse();

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

      /** 가격기준 Y축 생성 */
      // const valueAxisRight = chart.yAxes.push(new am4charts.ValueAxis());
      // valueAxisRight.renderer.opposite = true;
      // valueAxisRight.renderer.grid.template.disabled = true;
      // valueAxisRight.min = 0;
      // valueAxisRight.fontSize = '12px';

      const seriesColors = [
        '#FF7A00',
        '#FFEA53',
        '#3BABFF',
        '#FF4EB8',
        '#7232FB',
      ];
      const seriesDataFields = [
        {
          valueY: 'ratio_gpu',
          data: dataSets[0],
          total: 'total_gpu',
          used: 'used_gpu',
          label: 'GPU',
          unit: 'EA',
        },
        {
          valueY: 'ratio_cpu',
          data: dataSets[1],
          total: 'total_cpu',
          used: 'used_cpu',
          label: 'CPU',
          unit: 'Cores',
        },
        {
          valueY: 'ratio_ram',
          data: dataSets[2],
          total: 'total_ram',
          used: 'used_ram',
          label: 'RAM',
          unit: 'GB',
        },

        {
          valueY: 'ratio_storage_data',
          data: dataSets[3],
          total: 'total_storage_data',
          used: 'used_storage_data',
          label: 'Data Storage',
          unit: 'GB',
        },
        {
          valueY: 'ratio_storage_main',
          data: dataSets[4],
          total: 'total_storage_main',
          used: 'used_storage_main',
          label: 'Main Storage',
          unit: 'GB',
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
        }} ${seriesField.unit} / [bold]{${seriesField.total}} ${
          seriesField.unit
        } [bold]{valueY}%`;
        lineSeries.tooltip.getFillFromObject = false;
        lineSeries.tooltip.background.fill = am4core.color('#ffffff');
        lineSeries.tooltip.label.fill = am4core.color('#000');
        lineSeries.fill = am4core.color(seriesColors[index]);
        lineSeries.fillOpacity = 0; // 배경색 없음
        lineSeries.stroke = am4core.color(seriesColors[index]);
        lineSeries.strokeOpacity = 1;
        lineSeries.strokeWidth = 3;

        const bullet = lineSeries.bullets.push(new am4charts.CircleBullet());
        bullet.circle.radius = 0; // 선으로 표시하는 방법
        bullet.circle.fill = am4core.color('#ffffff');
        bullet.circle.stroke = am4core.color(seriesColors[index]);
        bullet.circle.strokeWidth = 3;
      });

      /** 가격 기준 */
      // const pricingSeries = chart.series.push(new am4charts.LineSeries());
      // pricingSeries.dataFields.dateX = 'date';
      // pricingSeries.dataFields.valueY = 'pricing';
      // pricingSeries.data = dataSets[5].reverse();
      // pricingSeries.name = 'pricing';
      // pricingSeries.yAxis = valueAxisRight;
      // pricingSeries.tooltipText = `{name}: [bold]{valueY}`;
      // pricingSeries.tooltip.getFillFromObject = false;
      // pricingSeries.tooltip.background.fill = am4core.color('#ffffff');
      // pricingSeries.tooltip.label.fill = am4core.color('#000');
      // pricingSeries.fill = am4core.color('#8e44ad');
      // pricingSeries.fillOpacity = 0.1;
      // pricingSeries.stroke = am4core.color('#8e44ad');
      // pricingSeries.strokeOpacity = 1;
      // pricingSeries.strokeWidth = 3;

      // const pricingBullet = pricingSeries.bullets.push(
      //   new am4charts.CircleBullet(),
      // );
      // pricingBullet.circle.radius = 6;
      // pricingBullet.circle.fill = am4core.color('#ffffff');
      // pricingBullet.circle.stroke = am4core.color('#8e44ad');
      // pricingBullet.circle.strokeWidth = 3;

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
      // totalUsage.pricing,
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

export default WorkSpaceResourceChart;
