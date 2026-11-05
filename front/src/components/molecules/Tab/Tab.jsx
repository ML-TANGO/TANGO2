// i18n
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './Tab.module.scss';
const cx = classNames.bind(style);

const Tab = ({
  option,
  select,
  tabHandler,
  type = 'a',
  sidePaddingNone,
  children,
  backgroudColor = '#fbfcff',
}) => {
  const { t } = useTranslation();
  let selectedCustomStyle = {};
  if (type === 'a') {
    selectedCustomStyle = { borderBottom: `1px solid ${backgroudColor}` };
  }
  return (
    <ul
      className={cx(
        'tab-controller',
        type === 'a' && 'type-a',
        type === 'b' && 'type-b',
        type === 'c' && 'type-c',
        sidePaddingNone && 'side-padding-none',
      )}
    >
      {option.map(({ label, value, disable, icon }, key) => (
        <li className={cx('tab', disable && 'disable')} key={key}>
          <button
            onClick={() => {
              if (!disable) tabHandler({ label, value });
            }}
            className={cx('tab-btn', select.value === value && 'selected')}
            style={select.value === value ? selectedCustomStyle : {}}
          >
            <div className={cx('tab-title')}>
              {icon && <img src={icon} alt='icon' />}
              {t(label)}
            </div>
          </button>
        </li>
      ))}
      {children}
    </ul>
  );
};

export default Tab;
