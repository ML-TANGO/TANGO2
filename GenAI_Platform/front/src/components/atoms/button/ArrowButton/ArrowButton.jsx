// CSS Module
import classNames from 'classnames/bind';
import style from './ArrowButton.module.scss';
const cx = classNames.bind(style);

/**
 *
 * @returns
 */
function ArrowButton({
  children,
  isUp = false,
  color = 'blue', // blue | white | grey
  onClick = () => {},
}) {
  return (
    <button className={cx('arrow-btn', color)} onClick={onClick}>
      {children && <span className={cx('text', color)}>{children}</span>}
      <img
        src={
          isUp
            ? `/images/icon/00-ic-basic-arrow-02-down-${color}.svg`
            : `/images/icon/00-ic-basic-arrow-02-up-${color}.svg`
        }
        alt='icon'
      />
    </button>
  );
}

export default ArrowButton;
