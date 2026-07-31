import { useTranslation } from 'react-i18next';

import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';

import { convertBinaryByte } from '@src/utils';

import Stack from '../../../AdminNodeContent/nodeComponent/NodeRateList/Stack';

import classNames from 'classnames/bind';
import style from './StorageIndividualItem.module.scss';

const cx = classNames.bind(style);

const StorageIndividualItem = ({
  title,
  storageList = [],
  totalSize,
  ...rest
}) => {
  const { t } = useTranslation();

  return (
    <div className={cx('individual-storage-cont')} {...rest}>
      <div className={cx('header')}>{title}</div>
      <div className={cx('contents-list')}>
        {storageList.map((info, idx) => {
          const { percentage } = calPercent(totalSize, info.alloc_size);
          const { percentage: barPercentage } = calPercent(
            totalSize,
            info.used_size,
          );
          return (
            <div
              className={cx(
                'contents-item',
                storageList.length > 5 && 'last-border-none',
              )}
              key={idx}
            >
              <div className={cx('item-header')}>
                <div className={cx('left-header')}>
                  <span className={cx('workspace-name-txt')}>
                    {info.workspace_name}
                  </span>
                  <span className={cx('allocate-txt')}>
                    {t('allocateGpu.label')}
                  </span>
                  <span className={cx('allocate-unit')}>
                    {convertBinaryByte(info.alloc_size)}
                  </span>
                </div>
                <div className={cx('right-header')}>{percentage}%</div>
              </div>
              <div className={cx('item-contents')}>
                <div className={cx('upper-item')}>
                  <div className={cx('upper-left-item')}>
                    <span>{t('used.label')}</span>
                    <span>{convertBinaryByte(info.used_size)}</span>
                  </div>
                  <div className={cx('upper-right-item')}>
                    ({convertBinaryByte(info.used_size)} /{' '}
                    {convertBinaryByte(totalSize)})
                  </div>
                </div>
                <Stack rate={barPercentage} isRateLabel={false} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default StorageIndividualItem;
