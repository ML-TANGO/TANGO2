// i18n
import { withTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
// CSS module
import style from './SubMenuItem.module.scss';

const cx = classNames.bind(style);

const SubMenuItem = ({
  option,
  select,
  onChangeHandler,
  responsive = false,
  customStyle,
  labelHeight,
  size = 'medium',
  t,
}) => {
  return (
    <div
      className={cx('sub-menu', size, responsive && 'responsive')}
      style={customStyle}
    >
      {option.map(({ label, value, icon }) => (
        <div key={value} className={cx('menu-item')}>
          <input
            type='radio'
            id={`type-${value}`}
            name='type'
            value={value}
            checked={select.value === value}
            className={cx('hide-input')}
            onChange={() => {
              onChangeHandler({ label, value });
            }}
          />
          <label
            htmlFor={`type-${value}`}
            className={cx('btn', select.value === value && 'selected')}
            style={labelHeight}
          >
            {t(label)}
          </label>
        </div>
      ))}
    </div>
  );
};

export default withTranslation()(SubMenuItem);
