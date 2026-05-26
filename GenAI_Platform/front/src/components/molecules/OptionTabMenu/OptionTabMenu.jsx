// CSS module
import style from './OptionTabMenu.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

/**
 * tab 형태의 버튼 리스트 메뉴
 *
 * @param {object} option
 *  [{label: '', value: '', icon: [defaultIconSrc, activeIconSrc]}, disabled: false, ...]
 * @param {string} selected
 * @param {Function} onChangeHandler
 * @returns
 */
function OptionTabMenu({ option, selected, onChangeHandler }) {
  return (
    <div className={cx('sub-menu')}>
      {option.map(({ label, value, icon, disabled }) => (
        <div key={value} className={cx('menu-item')}>
          <input
            type='radio'
            id={`type-${value}`}
            name='type'
            value={value}
            checked={selected === value}
            className={cx('hide-input')}
            onChange={() => onChangeHandler({ label, value })}
            disabled={disabled}
          />
          <label
            htmlFor={`type-${value}`}
            className={cx(
              'btn',
              selected === value && 'selected',
              disabled ? 'disabled' : '',
            )}
          >
            {icon && (
              <img
                className={cx('label-icon')}
                src={selected === value ? icon[1] : icon[0]}
                alt={label}
              />
            )}
            {label}
          </label>
        </div>
      ))}
    </div>
  );
}

export default OptionTabMenu;
