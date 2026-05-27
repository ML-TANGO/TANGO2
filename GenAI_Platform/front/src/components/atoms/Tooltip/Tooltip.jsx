// Icon

import { Balloon } from '@jonathan/ui-react';

import AlertIcon from '@src/static/images/icon/00-ic-alert-info-o.svg';
import React, { useRef, useState } from 'react';
import ReactDOM from 'react-dom';

import classnames from 'classnames/bind';
import style from './Tooltip.module.scss';

const cx = classnames.bind(style);

function Tooltip({
  children = undefined,
  customStyle = undefined,
  icon = AlertIcon,
  iconAlign = 'left',
  label,
  title,
  contents,
  contentsAlign,
  globalCustomStyle,
  iconCustomStyle,
  labelCustomStyle,
  contentsCustomStyle,
  type = 'light',
  isTail,
}) {
  const tooltipRef = useRef(null);

  const [isOpen, setIsOpen] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });

  const tooltipHandler = (flag) => {
    if (flag === true || flag === false) {
      setIsOpen(flag);
    } else {
      setIsOpen((isOpen) => !isOpen);
    }
  };

  const handleMouseEnter = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPosition({
      top: rect.top + window.scrollY + rect.height,
      left: rect.left + window.scrollX,
    });
    tooltipHandler(true);
  };

  const handleMouseOut = () => {
    tooltipHandler(false);
  };

  const renderIcon = (iconProp) => {
    return <img src={iconProp} alt='icon' style={iconCustomStyle} />;
  };

  return (
    <div
      className={cx('tooltip-wrap')}
      ref={tooltipRef}
      style={globalCustomStyle}
    >
      <div
        className={cx('tooltip-btn')}
        style={customStyle}
        onMouseEnter={handleMouseEnter}
        onMouseOut={handleMouseOut}
        onTouchStart={() => {
          tooltipHandler(true);
        }}
        onTouchEnd={() => {
          tooltipHandler(false);
        }}
      >
        {!children ? (
          <>
            {iconAlign === 'left' &&
              // <img src={icon} alt='HistoryIcon' style={iconCustomStyle} />
              renderIcon(icon)}
            {label && (
              <label className={cx('label')} style={labelCustomStyle}>
                {label}
              </label>
            )}
            {iconAlign === 'right' &&
              // <img src={icon} alt='icon' style={iconCustomStyle} />
              renderIcon(icon)}
          </>
        ) : (
          children
        )}
      </div>
      {isOpen &&
        ReactDOM.createPortal(
          <Balloon
            title={title}
            contents={contents}
            customStyle={{
              ...contentsCustomStyle,
              position: 'absolute',
              top: `${tooltipPosition.top}px`,
              left: `${tooltipPosition.left}px`,
              zIndex: '9999999',
            }}
            contentsAlign={contentsAlign}
            type={type}
            isTail={isTail}
            tooltipHandler={tooltipHandler}
          />,
          document.body,
        )}
    </div>
  );
}

// 컬러 주입

export default Tooltip;
