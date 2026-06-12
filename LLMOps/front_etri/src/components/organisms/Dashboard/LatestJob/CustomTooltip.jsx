import React, { useState } from 'react';

import classNames from 'classnames/bind';
import style from './CustomTooltip.module.scss';

const cx = classNames.bind(style);

const CustomTooltip = ({
  icon,
  contents,
  position,
  customStyle = {},
  iconStyle = {},
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
      <img src={icon} alt='' width={20} height={20} style={iconStyle} />
      {isVisible && (
        <div style={customStyle} className={cx('content-box', position)}>
          {contents}
        </div>
      )}
    </div>
  );
};

export default CustomTooltip;
