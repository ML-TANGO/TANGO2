// CSS Module
import classNames from 'classnames/bind';
import style from './ContextPopupBtn.module.scss';
const cx = classNames.bind(style);

/**
 *
 * @param {string | JSX.Element} children
 * @returns
 */
function ContextPopupBtn({
  children,
  isOpen,
  popupHandler,
  disableArrow,
  customStyle = {},
}) {
  return (
    <button
      className={cx('btn', isOpen && 'active')}
      onClick={(e) => {
        e.stopPropagation();
        popupHandler();
      }}
      style={customStyle}
    >
      {children}
      {!disableArrow && (
        <img
          src={`/images/icon/${
            isOpen
              ? '00-ic-basic-arrow-02-up-white.svg'
              : '00-ic-basic-arrow-02-down-white.svg'
          }`}
          className={cx('arrow')}
          alt='arrow-icon'
        />
      )}
    </button>
  );
}

export default ContextPopupBtn;
