import React, { useState } from 'react';

import classNames from 'classnames/bind';
import style from './ProcessToolTip.module.scss';

const cx = classNames.bind(style);

const ProcessToolTip = ({
  icon,
  contents,
  position,
  customStyle = {},
  iconStyle = {},
  iconWidth = 20,
  iconHeight = 20,
}) => {
  const [isVisible, setIsVisible] = useState(false);

  const showTooltip = () => {
    setIsVisible(true);
  };

  const hideTooltip = () => {
    setIsVisible(false);
  };

  return (
    <div
      className={cx('container')}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
    >
      <img
        src={icon}
        alt=''
        width={iconWidth}
        height={iconHeight}
        style={iconStyle}
      />
      {isVisible && (
        <div style={customStyle} className={cx('content-box', position)}>
          {contents}
        </div>
      )}
    </div>
  );
};

export default ProcessToolTip;
