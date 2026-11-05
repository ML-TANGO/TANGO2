import React, { useRef, useState } from 'react';

import TooltipPortal from '@src/hooks/TooltipPortal';

import { BAR_COLOR } from '../ListStack';

import classNames from 'classnames/bind';
import style from './PartStack.module.scss';

const cx = classNames.bind(style);

const PartStack = ({
  idx,
  isTooltip = false,
  tooltipDirection = 'top',
  tooltipContent,
  width,
  color,
}) => {
  const stackRef = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  return (
    <React.Fragment key={`${idx}`}>
      <div
        ref={stackRef}
        className={cx('stack-part-cont')}
        style={{
          width: `${width >= 0 ? width : 0}px`,
          backgroundColor: color ? color : BAR_COLOR[idx],
        }}
        onMouseEnter={() => setIsShowTooltip(true)}
        onMouseLeave={() => setIsShowTooltip(false)}
      />
      <TooltipPortal
        direction={tooltipDirection}
        targetRef={stackRef}
        isShowTooltip={isShowTooltip}
      >
        {isTooltip && tooltipContent}
      </TooltipPortal>
    </React.Fragment>
  );
};

export default PartStack;
