import React, { useEffect, useRef, useState } from 'react';

import TooltipPortal from '@src/hooks/TooltipPortal';

import downArrow from '/images/icon/ic-arrow-gray-down.svg';
import upArrow from '/images/icon/ic-arrow-gray-up.svg';

import { handleMoveToScroll } from '@src/utils';

import classNames from 'classnames/bind';
import style from './FixGrayDropDown.module.scss';

const cx = classNames.bind(style);

const FixGrayDropDown = ({
  placeholder = '',
  list,
  value,
  handleSelectOption,
  customStyle = {},
  isCloseBorder = true,
  listCustomStyle = {},
  isReadOnly = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const selectContRef = useRef(null);

  return (
    <div
      className={cx('container', isReadOnly && 'isReadOnly')}
      style={customStyle}
      ref={selectContRef}
    >
      <div
        className={cx(
          'default-box',
          isOpen && 'isOpen',
          value.label !== '' && !isOpen && isCloseBorder && 'isSelected',
        )}
        onClick={() => {
          if (!isReadOnly) {
            setIsOpen((prev) => !prev);
          }
        }}
      >
        {value.label ? (
          <span className={cx('label')}>{value.label}</span>
        ) : (
          `${placeholder}`
        )}
        <img
          src={isOpen ? upArrow : downArrow}
          alt='arrow'
          className={cx('arrow-btn')}
        />
      </div>
      {isOpen && (
        <div className={cx('list-box')} style={{ ...listCustomStyle }}>
          {list.map(({ value, label }, index) => (
            <div
              id={`dropdown-${value}`}
              className={cx('list')}
              onClick={() => {
                setIsOpen((prev) => !prev);
                handleSelectOption({ label, value });
              }}
              key={index}
            >
              {label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FixGrayDropDown;
