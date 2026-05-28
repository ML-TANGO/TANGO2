import React from 'react';

import Stack from '../../AdminNodeContent/nodeComponent/NodeRateList/Stack';

import classNames from 'classnames/bind';
import style from './AllStorageStack.module.scss';

const cx = classNames.bind(style);

const calSplitUnit = (sizeValue) => {
  const splitData = sizeValue.split(' ');
  if (splitData.length !== 2) return ['', ''];

  const value = splitData[0];
  const unit = splitData[1];
  return [value, unit];
};

const AllStorageStack = React.memo(
  ({ label, labelValue, totalSize, percentage }) => {
    const [totalValue, totalUnit] = calSplitUnit(totalSize);
    const [splitLabelValue, labelUnit] = calSplitUnit(labelValue);

    return (
      <div className={cx('allocate-cont')}>
        <div className={cx('stack-cont')}>
          <div className={cx('label-cont')}>
            <span className={cx('label')}>{label}</span>
            <span className={cx('value')}>{labelValue}</span>
          </div>
          <Stack
            rate={percentage}
            isRateLabel={false}
            tooltipContent={
              <div
                style={{
                  display: 'flex',
                  gap: '8px',
                  fontFamily: 'SpoqaB',
                  fontSize: '10px',
                }}
              >
                <span>{label}</span>
                <span>{labelValue}EA</span>
              </div>
            }
          />
        </div>
        <div className={cx('percent-label-cont')}>
          <span className={cx('percent-txt')}>{percentage} %</span>
          <span className={cx('special-txt')}>(</span>
          <span className={cx('value-txt')}>{splitLabelValue}</span>
          <span className={cx('unit-txt')}>{labelUnit}</span>
          <span className={cx('special-txt')}>/</span>
          <span className={cx('value-txt')}>{totalValue}</span>
          <span className={cx('unit-txt')}>{totalUnit}</span>
          <span className={cx('special-txt')}>)</span>
        </div>
      </div>
    );
  },
);

export default AllStorageStack;
