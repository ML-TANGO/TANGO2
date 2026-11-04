// i18n
import { useTranslation } from 'react-i18next';

// Atoms
import SwitchBtn from '@src/components/atoms/checkbox/SwitchBtn';

// CSS Module
import classNames from 'classnames/bind';
import style from './SwitchFilterMenu.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

/**
 * 드랍 메뉴의 팝업 영역에 쓰이는 필터 목록 컴포넌트
 * @component
 * @example
 *
 * cosnt filterList = [
 *    { name: 'Activated', checked: false, iconPath: 'image-url' },
 *    { name: 'Show hiddens', checked: false, iconPath: 'image-url' },
 *    { name: 'Built-in only', checked: false, iconPath: 'image-url' },
 * ];
 *
 * return (
 *  <SwitchFilterMenu
 *    filterList={filterList}
 *    onChange={onChange}
 *  />
 * );
 */
function SwitchFilterMenu({ filterList = [], onChange = noop }) {
  const { t } = useTranslation();

  return (
    <ul className={cx('switch-filter-list')}>
      {filterList.map(({ name, checked, iconPath }, key) => (
        <li className={cx('switch-filter')} key={key}>
          {/* 아이콘 */}
          {iconPath && (
            <img className={cx('icon')} src={iconPath} alt='filter icon' />
          )}
          {/* 필터 이름 */}
          {<span className={cx('filter-name')}>{t(name)}</span>}
          {/* 스위치 버튼 */}
          <SwitchBtn
            checked={checked}
            onChange={() => {
              onChange(key, checked);
            }}
          />
        </li>
      ))}
    </ul>
  );
}

export default SwitchFilterMenu;
