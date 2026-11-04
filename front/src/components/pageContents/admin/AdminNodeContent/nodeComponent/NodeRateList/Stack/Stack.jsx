import React, { useRef, useState } from 'react';

import TooltipPortal from '@src/hooks/TooltipPortal';

// CSS Module
import classNames from 'classnames/bind';
import style from './Stack.module.scss';

const cx = classNames.bind(style);

const Stack = React.memo(
  ({ rate, isRateLabel = true, isTooltip = false, tooltipContent }) => {
    const targetRef = useRef(null);
    const [isShowTooltip, setIsShowTooltip] = useState(false);

    return (
      <div className={cx('stack-wrap')}>
        <div className={cx('stack')}>
          <div
            ref={targetRef}
            className={cx(
              'fill',
              rate >= 90 && 'danger',
              rate >= 70 && rate <= 89 && 'warn',
            )}
            style={{ width: `${rate}%` }}
            onMouseEnter={() => setIsShowTooltip(true)}
            onMouseLeave={() => setIsShowTooltip(false)}
          />
          <TooltipPortal
            direction='bottom'
            targetRef={targetRef}
            isShowTooltip={isShowTooltip}
          >
            {isTooltip && tooltipContent}
          </TooltipPortal>
        </div>
        {isRateLabel && (
          <span className={cx('rate')}>
            {rate !== null ? (
              `${Math.floor(rate)}%`
            ) : (
              <span className={cx('error')}>error</span>
            )}
          </span>
        )}
      </div>
    );
  },
);

export default Stack;
