// i18n
import { withTranslation } from 'react-i18next';
import { PieChart as MinimalPieChart } from 'react-minimal-pie-chart';

import classNames from 'classnames/bind';
// CSS Module
import style from './NewPieChart.module.scss';

const cx = classNames.bind(style);

const colors = ['#56A8D4', '#557FD4', '#5458D4', '#6C4DD3', '#904CD4'];

const NewPieChart = ({
  width,
  height,
  data,
  total,
  legend,
  isLabelCeneter,
  label,
  labelStyle,
  chartTitle,
  pcent,
  additionalData,
  lineWidth = 48,
  typeLabel,
  numberPercent,
  t,
}) => {
  const getBarColor = (percent) => {
    if (percent >= 0 && percent <= 25) return '#2D76F8';
    if (percent > 25 && percent <= 50) return '#02E366';
    if (percent > 50 && percent <= 75) return '#FFEA53';
    if (percent > 75) return '#FF3B30';
  };

  const parsePieChartData = () => {
    const result = [];
    for (let i = 0; i < data.length; i += 1) {
      const d = data[i];
      result.push({
        ...d,
        title: t(d.title),
        color: getBarColor(numberPercent),
      });
    }
    return result;
  };
  const tmpData = parsePieChartData();
  const propsObj = {};
  if (isLabelCeneter) {
    propsObj.labelPosition = 0;
  }
  if (label)
    propsObj.label = ({ dataEntry }) =>
      dataEntry.value !== 0 && dataEntry.title;
  return (
    <div className={cx('pie-chart-wrap')}>
      <div className={cx('chart-wrap')}>
        <div className={cx('chart')} style={{ width, height }}>
          <MinimalPieChart
            data={tmpData}
            totalValue={total}
            labelStyle={labelStyle}
            background='#ececec'
            lineWidth={lineWidth}
            {...propsObj}
          />
          {pcent && (
            <div className={cx('pcent')}>
              <span>{typeLabel}</span>
              <span>{pcent}</span>
            </div>
          )}
        </div>
        {legend && (
          <ul className={cx('legend')}>
            <li className={cx('legend-item')}>
              <span className={cx('legend-text', 'total')}>
                {t('total.label')} : {total}
              </span>
            </li>
            {tmpData.map(({ title, value, color, icon }, key) => (
              <li key={key} className={cx('legend-item')}>
                <i
                  className={cx('color-i')}
                  style={{ backgroundColor: color }}
                ></i>
                <span className={cx('legend-text')}>
                  {t(title)} : {value}
                </span>
                {icon}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className={cx('chart-title')}>{t(chartTitle)}</p>
    </div>
  );
};
export default withTranslation()(NewPieChart);
