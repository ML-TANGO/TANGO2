import React, { useEffect, useState } from 'react';

import useOutsideClick from '@src/hooks/useOutsideClick';

import { handleMoveToScroll } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './SelectBox.module.scss';

import IconArrow from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';

const cx = classNames.bind(style);

const handleTransformOption = (
  isDisabled,
  option,
  setIsOpen,
  handleOptionClick,
) => {
  if (isDisabled) return;
  handleOptionClick(option);
  setIsOpen(false);
};

const handleToggleDropdown = (setIsOpen, disabled) => {
  if (disabled) return;
  setIsOpen((prev) => !prev);
};

const SelectBox = ({
  placeholder = '',
  value,
  list,
  handleOptionClick,
  disabled,
  ...rest
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const selectedOptionValue = list.find((el) => el.value === value);

  const { ref: outSideRef } = useOutsideClick(() => setIsOpen(false));

  useEffect(() => {
    if (isOpen && value) {
      handleMoveToScroll(`dropdown-${value}`, 'smooth');
    }
  }, [isOpen, value]);

  return (
    <div ref={outSideRef} style={{ position: 'relative' }}>
      <div
        className={cx(
          'dropdown-header',
          isOpen && 'open',
          disabled && 'disabled',
        )}
        onClick={() => handleToggleDropdown(setIsOpen, disabled)}
        {...rest}
      >
        <div
          className={cx(
            'content',
            !selectedOptionValue && 'placeholder',
            disabled && 'disabled',
          )}
        >
          {selectedOptionValue ? (
            <>
              {selectedOptionValue.frontContent && (
                <div className={cx('front')}>
                  {selectedOptionValue.frontContent}
                </div>
              )}
              {selectedOptionValue.label && (
                <div className={cx('label')}>{selectedOptionValue.label}</div>
              )}
            </>
          ) : (
            <>{placeholder}</>
          )}
        </div>
        <img
          className={cx('arrow', isOpen && 'open')}
          src={IconArrow}
          alt='arrow'
        />
      </div>
      {isOpen && (
        <ul
          className={cx('dropdown-list')}
          style={{
            width: `${rest.style?.width}`,
          }}
        >
          {list.map((item, idx) => (
            <li
              id={`dropdown-${item.value}`}
              key={item.value}
              className={cx(
                item.value === value && 'selected',
                idx > 3 && 'none-bt-border-last-index',
                item.disabled && 'disabled',
              )}
              onClick={() =>
                handleTransformOption(
                  item.disabled,
                  item,
                  setIsOpen,
                  handleOptionClick,
                )
              }
              style={{
                ...rest.style,
                width: `${rest.style.width - 2}px`,
              }}
            >
              {item.frontContent && (
                <div className={cx('front')}>{item.frontContent}</div>
              )}
              <div className={cx('item-txt')}>{item.label}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default SelectBox;
