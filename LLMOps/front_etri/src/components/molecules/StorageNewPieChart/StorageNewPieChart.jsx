import { Tooltip } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

// Components
import NewPieChart from './NewPieChart';

// CSS Module
import classNames from 'classnames/bind';
import style from './StorageNewPieChart.module.scss';

const cx = classNames.bind(style);

function StorageNewPieChart({
  label,
  value,
  total,
  title,
  titleStyle,
  used,
  pcent,
  totalSize,
  fontSize,
  additionalData = [],
  increaseClickCount,
  allocationSize,
  remainSize,
  typeLabel,
  numberPercent,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('node-pie-chart')}>
      <div className={cx('chart-container')}>
        <div onClick={increaseClickCount}>
          <NewPieChart
            numberPercent={numberPercent}
            width={'130px'}
            height={'130px'}
            data={
              additionalData.length > 0
                ? [...additionalData]
                : [{ label, value, color: '#2D76F8' }]
            }
            pcent={pcent}
            total={total}
            lineWidth={16}
            typeLabel={typeLabel}
          />
        </div>
      </div>

      <div className={cx('info')}>
        <div className={cx('label')}>
          <span>{t('storageAllocationSize.label')}</span>
          <span>{t('storagUsage.label')}</span>
          <span>{t('storageAvailable.label')}</span>
        </div>
        <div className={cx('detail')}>
          <span>{allocationSize}</span>
          <span>{used}</span>
          <span>{remainSize}</span>
        </div>
      </div>
    </div>
  );
}

export default StorageNewPieChart;
