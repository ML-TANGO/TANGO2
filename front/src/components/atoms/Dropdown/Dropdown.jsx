import { useEffect, useRef, useState } from 'react';

import TooltipPortal from '@src/hooks/TooltipPortal';

import { handleMoveToScroll } from '@src/utils';

import classNames from 'classnames/bind';
import style from './Dropdown.module.scss';

import IconArrow from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';

const cx = classNames.bind(style);

const handleTransformOption = (option, setIsOpen, handleOptionClick, e) => {
  handleOptionClick(option, e);
  setIsOpen(false);
};

const handleToggleDropdown = (setIsOpen, isOpen, disabled) => {
  if (disabled) return;
  setIsOpen(!isOpen);
};

const Dropdown = ({
  placeholder = '',
  value,
  list,
  handleOptionClick,
  disabled,
  ...rest
}) => {
  const [width, setWidth] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  const selectContRef = useRef(null);

  const selectedOptionValue = list.find((el) => el.value === value);

  useEffect(() => {
    if (isOpen && value) {
      handleMoveToScroll(`dropdown-${value}`, 'smooth');
    }
  }, [isOpen, value]);

  useEffect(() => {
    const box = selectContRef.current;
    if (!box) return;

    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width } = entry.contentRect;
        const { paddingLeft, paddingRight } = window.getComputedStyle(box);
        setWidth(
          Number(width) +
            parseFloat(paddingLeft) +
            parseFloat(paddingRight) +
            2,
        );
        setIsOpen(false);
      }
    });

    const handleClickOutside = (event) => {
      if (
        selectContRef.current &&
        !selectContRef.current.contains(event.target)
      ) {
        if (event.srcElement.parentNode.localName === 'ul') return;
        if (event.srcElement.parentNode.localName === 'li') return;
        if (event.target.localName === 'li') return;
        setIsOpen(false);
      }
    };

    observer.observe(box);
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      observer.unobserve(box);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <>
      <div
        ref={selectContRef}
        className={cx(
          'dropdown-header',
          isOpen && 'open',
          disabled && 'disabled',
        )}
        onClick={() => handleToggleDropdown(setIsOpen, isOpen, disabled)}
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
      <TooltipPortal
        direction='bottom'
        targetRef={selectContRef}
        isShowTooltip={isOpen}
      >
        <ul className={cx('dropdown-list')} style={{ width: `${width}px` }}>
          {list.map((item, idx) => (
            <li
              id={`dropdown-${item.value}`}
              key={`${item.value}-${idx}`}
              className={cx(
                item.value === value && 'selected',
                idx > 3 && 'none-bt-border-last-index',
              )}
              onClick={(e) => {
                e.stopPropagation();
                handleTransformOption(item, setIsOpen, handleOptionClick, e);
              }}
              style={{
                ...rest.style,
              }}
            >
              {item.frontContent && (
                <div className={cx('front')}>{item.frontContent}</div>
              )}
              <div className={cx('item-txt')}>{item.label}</div>
            </li>
          ))}
        </ul>
      </TooltipPortal>
    </>
  );
};

export default Dropdown;
