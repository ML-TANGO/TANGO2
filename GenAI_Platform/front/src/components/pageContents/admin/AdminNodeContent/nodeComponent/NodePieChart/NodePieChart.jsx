import { memo } from 'react';
import { useTranslation } from 'react-i18next';

// Components
import CircleGauge from '@src/components/molecules/CircleGauge';
import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';

// CSS Module
import classNames from 'classnames/bind';
import style from './NodePieChart.module.scss';

const cx = classNames.bind(style);

const NodePieChart = memo(({ value, total, title }) => {
  const { t } = useTranslation();
  const { percentage } = calPercent(total, value);
  return (
    <div className={cx('node-pie-chart')}>
      <p className={cx('title')}>{title}</p>
      <div className={cx('content-cont')}>
        <div className={cx('chart-cont')}>
          <CircleGauge percentage={percentage} />
          <span className={cx('percent-txt')}>{percentage ?? 0}%</span>
        </div>
        <div className={cx('label-cont')}>
          <div className={cx('row')}>
            <span className={cx('label')}>{t('total.label')}</span>
            <span className={cx('value')}>{total ?? 0} Cores</span>
          </div>
          <div className={cx('row')}>
            <span className={cx('label')}>{t('allocateGpu.label')}</span>
            <span className={cx('value')}>{value ?? 0} Cores</span>
          </div>
          <div className={cx('row')}>
            <span className={cx('label')}>{t('storageAvailable.label')}</span>
            <span className={cx('value')}>{value ?? 0} Cores</span>
          </div>
          <div className={cx('row')}>
            <span className={cx('label')}>{t('enable.label')}</span>
            <span className={cx('value')}>{total - value ?? 0} Cores</span>
          </div>
        </div>
        {/* <div className={cx('legend')}>
          <div className={cx('item')}>
            <span className={cx('val')}>{value}</span>
            <span className={cx('label')}>
              <span className={cx('bullet')}>{label}</span>
            </span>
          </div>
          <div className={cx('item')}>
            <span className={cx('val')}>{total}</span>
            <span className={cx('label')}>{t('total.label')}</span>
          </div>
        </div> */}
      </div>
    </div>
  );
});

export default NodePieChart;
