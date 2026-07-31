import { useEffect, useCallback } from 'react';

// i18n
import { withTranslation } from 'react-i18next';

// Chart lib
import * as am4core from '@amcharts/amcharts4/core';
import * as am4charts from '@amcharts/amcharts4/charts';
import am4themesAnimated from '@amcharts/amcharts4/themes/animated';

// Components
import EmptyBox from '@src/components/molecules/EmptyBox';

am4core.useTheme(am4themesAnimated);
let chart;
const TreeMapChart = ({
  tagId,
  data,
  tooltipText,
  label,
  value,
  customStyle = { height: '600px' },
  t,
}) => {
  const generateChart = useCallback(() => {
    if (!document.getElementById(tagId) || data.length === 0) return;
    chart = am4core.create(tagId, am4charts.TreeMap);
    chart.hiddenState.properties.opacity = 0;

    const newData = data.map((item) => ({
      [label]: item[label],
      children: [
        {
          ...item,
          [label]: item[label],
          [value]: item[value],
        },
      ],
    }));

    chart.data = newData;
    chart.paddingTop = 0;
    chart.paddingRight = 0;
    chart.paddingBottom = 0;
    chart.paddingLeft = 0;

    chart.colors.step = 2;

    chart.dataFields.value = value;
    chart.dataFields.name = label;
    chart.dataFields.children = 'children';

    chart.zoomable = false;
    const bgColor = new am4core.InterfaceColorSet().getFor('background');

    // level 0 series template
    const level0SeriesTemplate = chart.seriesTemplates.create('0');
    const level0ColumnTemplate = level0SeriesTemplate.columns.template;

    level0ColumnTemplate.column.cornerRadius(10, 10, 10, 10);
    level0ColumnTemplate.fillOpacity = 0;
    level0ColumnTemplate.strokeWidth = 4;
    level0ColumnTemplate.strokeOpacity = 0;

    // level 1 series template
    const level1SeriesTemplate = chart.seriesTemplates.create(1);
    level1SeriesTemplate.tooltip.animationDuration = 0;
    level1SeriesTemplate.strokeOpacity = 1;

    const level1ColumnTemplate = level1SeriesTemplate.columns.template;
    level1ColumnTemplate.tooltipText = tooltipText;
    // level1ColumnTemplate.tooltipText = '{name}: [bold]{value}[/]';
    level1ColumnTemplate.column.cornerRadius(10, 10, 10, 10);
    level1ColumnTemplate.fillOpacity = 1;
    level1ColumnTemplate.strokeWidth = 4;
    level1ColumnTemplate.stroke = bgColor;

    const bullet1 = level1SeriesTemplate.bullets.push(
      new am4charts.LabelBullet(),
    );
    bullet1.locationY = 0.5;
    bullet1.locationX = 0.5;
    bullet1.label.text = '{name}';
    bullet1.label.fill = am4core.color('#ffffff');

    chart.maxLevels = 5;
  }, [data, tagId, tooltipText, label, value]);

  useEffect(() => {
    generateChart();
    return () => {
      if (chart) chart.dispose();
    };
  }, [data, generateChart]);
  return (
    <>
      {data.length === 0 ? (
        <EmptyBox customStyle={customStyle} text={t('noChartData.message')} />
      ) : (
        <div id={tagId} style={customStyle}></div>
      )}
    </>
  );
};

export default withTranslation()(TreeMapChart);
