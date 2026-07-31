import { InputNumber, Tooltip } from '@tango/ui-react';
import StorageUsageBar from '../StorageUsageBar';
import StorageListItem from './StorageListItem/StorageListItem';

// CSS Module
import classNames from 'classnames/bind';
import style from './StorageBox.module.scss';
const cx = classNames.bind(style);

function StorageBox({
  list,
  t,
  storageSelectedOptions,
  onChangeStorageValue,
  checkboxHandler,
}) {
  return (
    <div className={cx('wrapper')}>
      <div className={cx('list-header')}>
        <div>{t('storageName.label')}</div>
        <div className={cx('sub-col')}>
          <div>{t('totalCapacity.label')}(GB)</div>
        </div>
        <div className={cx('sub-col')}>
          <div>{t('storageRemaining.modal.label')}(GB)</div>
        </div>
        <div className={cx('sub-col')}>
          <div>
            {t('allocationCapacity.label')}
            (GB)
          </div>
        </div>
      </div>

      <ul className={cx('list-body')}>
        {list && list.length > 0 ? (
          list.map(({ type, free_size: free, id, total_size: total }, idx) => {
            // gpuSelectedOptions,
            // gpuDetailSelectedOptions

            return (
              <StorageListItem
                key={idx}
                idx={idx}
                model={type}
                total={total}
                free={free}
                selected={storageSelectedOptions}
                checkboxHandler={checkboxHandler}
                onChangeInputValue={onChangeStorageValue}
                type={type}
              />
            );
          })
        ) : (
          <div className={cx('empty-item')}>{t('noData.message')}</div>
        )}
      </ul>
    </div>
  );
}

export default StorageBox;
