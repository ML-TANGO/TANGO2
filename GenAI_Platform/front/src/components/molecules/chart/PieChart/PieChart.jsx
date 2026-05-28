import { useEffect, useCallback } from 'react';
import * as am4core from '@amcharts/amcharts4/core';
import * as am4charts from '@amcharts/amcharts4/charts';
import am4themesAnimated from '@amcharts/amcharts4/themes/animated';

let chart;
const PieChart = ({ tagId, data = [], customStyle = {} }) => {
  /* 차트 포맷에 맞게 데이터 구조 변경 및 컬러 추가 */
  function makeChartData(originData) {
    const chartData = [];

    const colorList = [
      am4core.color('#69bfd4'),
      am4core.color('#5c7cd4'),
      am4core.color('#9573da'),
      am4core.color('#ce73d5'),
      am4core.color('#d76f98'),
      am4core.color('#e1907b'),
    ];

    originData.map((obj) => {
      const newObj = {};
      const name = Object.keys(obj)[0];
      const prob = Object.values(obj)[0];
      newObj.name = name;
      newObj.prob = prob;

      /* eslint-disable prefer-destructuring */
      if (name === '정상') {
        newObj.color = colorList[0];
      } else if (name === '물집') {
        newObj.color = colorList[1];
      } else if (name === '표면2도') {
        newObj.color = colorList[2];
      } else if (name === '중간2도') {
        newObj.color = colorList[3];
      } else if (name === '깊은2도') {
        newObj.color = colorList[4];
      } else if (name === '3도이상') {
        newObj.color = colorList[5];
      }
      return chartData.push(newObj);
    });
    return chartData;
  }

  const generateChart = useCallback(() => {
    if (!document.getElementById(tagId) || data.length === 0) return;
    const chartData = makeChartData(data);

    // 최대값 찾기
    // const topObj = chartData.reduce((prev, value) => {
    //   return prev.prob >= value.prob ? prev : value;
    // });
    // const topName = topObj.name;
    // const topProb = `${(topObj.prob * 100).toFixed(1)}%`;

    // Themes
    am4core.useTheme(am4themesAnimated);

    chart = am4core.create(tagId, am4charts.PieChart);

    chart.paddingTop = 0;
    chart.paddingBottom = 20;
    chart.paddingRight = 20;
    chart.paddingLeft = 0;

    // Data
    chart.data = chartData;

    // Add label
    const label = chart.seriesContainer.createChild(am4core.Label);
    // if (topName.length > 5) {
    //   // 글자수 길면 확률값 생략
    //   label.text = `[bold #232323 font-size:18px]${topName}[/]`;
    // } else {
    //   label.text = `[#232323 font-size:22px]${topName}[/] [bold #797979 font-size:16px]${topProb}[/]`;
    // }
    label.horizontalCenter = 'middle';
    label.verticalCenter = 'middle';
    label.fontSize = 24;

    // Add and configure Series
    const pieSeries = chart.series.push(new am4charts.PieSeries());
    pieSeries.dataFields.value = 'prob';
    pieSeries.dataFields.category = 'name';
    // pieSeries.innerRadius = am4core.percent(80); // 도넛
    pieSeries.ticks.template.disabled = true;
    pieSeries.labels.template.disabled = true;
    pieSeries.slices.template.strokeWidth = 0;
    pieSeries.slices.template.propertyFields.fill = 'color';

    // Add legend
    const legend = (chart.legend = new am4charts.Legend());
    legend.position = 'right';
    legend.valign = 'top';
    legend.fontSize = 16;
    legend.fontFamily = 'SpoqaM';
    legend.fontWeight = 500;
    legend.itemContainers.template.paddingTop = 6;
    legend.itemContainers.template.paddingBottom = 6;
    legend.itemContainers.template.paddingRight = 20;
    legend.itemContainers.template.paddingLeft = -20;
    legend.itemContainers.template.width = 300;
    legend.labels.template.text = '[#121619 font-size:16px]{name}[/]';
    legend.valueLabels.template.text =
      '[normal #3e3e3e font-size:16px]{value.percent.formatNumber("#.#")}%[/]';
    legend.labels.template.truncate = true;
    legend.labels.template.wrap = true;
    legend.useDefaultMarker = true;
    legend.maxWidth = 360;

    const marker = chart.legend.markers.template.children.getIndex(0);
    marker.cornerRadius(6, 6, 6, 6);

    const markerTemplate = chart.legend.markers.template;
    markerTemplate.width = 22;
    markerTemplate.height = 22;
    markerTemplate.marginRight = 12;
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

export default PieChart;
