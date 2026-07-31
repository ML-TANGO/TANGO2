// i18n
import { useTranslation } from 'react-i18next';
import {
  Sparklines,
  SparklinesBars,
  SparklinesReferenceLine,
  // SparklinesLine,
} from 'react-sparklines';

// CSS Module
import classNames from 'classnames/bind';
import style from './CallCountChart.module.scss';

const cx = classNames.bind(style);

function CallCountChart({ data }) {
  // 임시 주석
  const { t } = useTranslation();
  return (
    <div className={cx('chart-container')}>
      <div className={cx('chart-text-box')}>
        <label>{t('callCount.label')}</label>
        <span>{t('last24h.label')}</span>
      </div>
      {data.length > 0 ? (
        <Sparklines
          data={data}
          height={40}
          margin={2}
          min={0}
          max={Math.max(...data) + 1} // 0일 때 바닥에 깔리도록 max지정
        >
          <SparklinesBars style={{ fill: '#2d76f8', fillOpacity: '.25' }} />
          <SparklinesReferenceLine
            type='mean'
            style={{
              stroke: '#2d76f8',
              strokeOpacity: '.75',
              strokeDasharray: '2 2',
            }}
          />
          {/* <SparklinesLine style={{ stroke: '#5874f7', fill: 'none' }} /> */}
        </Sparklines>
      ) : (
        <div className={cx('empty-box')}></div>
      )}
    </div>
  );
}

export default CallCountChart;
