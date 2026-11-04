// CSS Module
import classNames from 'classnames/bind';
import style from './Button.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

/**
 * 버튼 컴포넌트 (Atom)
 * @param {{
 *  size: 'x-large' | 'large' | 'medium' | 'small' | 'x-small',
 *  type: 'primary' | 'transparent' | 'white'
 *        | 'secondary' | 'danger' | 'gray' | 'none-border',
 *  leftIcon: string,
 *  rightIcon: string,
 *  children: JSX.Element,
 *  customStyle: object,
 *  responsiveMode: boolean,
 *  disableHoverStyle: boolean,
 *  disabled: boolean,
 *  onClick: Function,
 * }} param0
 * @returns
 */
function Button({
  size = 'medium',
  type = 'secondary',
  leftIcon,
  rightIcon,
  children,
  customStyle = {},
  responsiveMode,
  disableHoverStyle,
  disabled,
  onClick = noop,
  testId,
}) {
  let content = '';
  if (responsiveMode) {
    if (leftIcon) {
      content = (
        <span className={cx('icon-wrap')}>
          <img className={cx('icon')} src={leftIcon} alt='' />
        </span>
      );
    } else if (rightIcon) {
      content = (
        <span className={cx('icon-wrap')}>
          <img className={cx('icon')} src={rightIcon} alt='' />
        </span>
      );
    }
  } else if ((leftIcon || rightIcon) && children) {
    content = (
      <span
        className={cx(
          'children-wrap',
          leftIcon && 'padding-left',
          rightIcon && 'padding-right',
        )}
      >
        {leftIcon && <img className={cx('icon')} src={leftIcon} alt='' />}
        {children && <span className={cx('text')}>{children}</span>}
        {rightIcon && <img className={cx('icon')} src={rightIcon} alt='' />}
      </span>
    );
  } else if (children) {
    content = (
      <span className={cx('text-wrap')}>
        <span className={cx('text')}>{children}</span>
      </span>
    );
  } else if (leftIcon) {
    content = (
      <span className={cx('icon-wrap')}>
        <img className={cx('icon')} src={leftIcon} alt='' />
      </span>
    );
  } else if (rightIcon) {
    content = (
      <span className={cx('icon-wrap')}>
        <img className={cx('icon')} src={rightIcon} alt='' />
      </span>
    );
  }
  return (
    <button
      className={cx(
        'fb',
        'btn',
        size,
        type,
        disableHoverStyle ? 'nohover' : '',
      )}
      style={customStyle}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
    >
      {content}
    </button>
  );
}

export default Button;
