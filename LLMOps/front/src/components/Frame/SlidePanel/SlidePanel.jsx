import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './SlidePanel.module.scss';
const cx = classNames.bind(style);

/**
 * 슬라이드 패널 컴포넌트
 * @component
 * @example
 * const panels = [
 *  { Comp: <div>component</div>, icon: '<image path>' },
 * ]
 * return (
 *  <SlidePanel panels={panels} />
 * )
 */
function SlidePanel({ panels }) {
  // 다국어 지원
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState(false);
  const [targetIdx, setTargetIdx] = useState(0);

  const panelHandler = (idx) => {
    setTargetIdx(idx);
    if (targetIdx === idx && isOpen) {
      setIsOpen(false);
    } else {
      setIsOpen(true);
    }
  };

  const pannelClose = () => {
    setIsOpen(false);
  };

  const TargetComp = panels[targetIdx].Comp;

  return (
    <div className={cx('panel', isOpen && 'open')}>
      <div className={cx('panel-header')}>
        <button className={cx('close-btn')} onClick={pannelClose}>
          <img src='/images/icon/close.svg' alt='panel close btn' />
        </button>
      </div>
      {panels.map(({ iconSrc }, key) => (
        <div
          key={key}
          className={cx(
            'panel-open-btn',
            key === targetIdx && isOpen && 'active',
          )}
          style={{ top: `${key === 0 ? 170 : 170 + 50 * key}px` }}
          onClick={() => {
            panelHandler(key);
          }}
        >
          <img
            src={`${iconSrc}${key === targetIdx && isOpen ? '_hover' : ''}.svg`}
            alt='open'
          />
        </div>
      ))}
      <div className={cx('content-box')}>
        {<TargetComp isOpen={isOpen} t={t} />}
      </div>
    </div>
  );
}

export default SlidePanel;
