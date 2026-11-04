// i18n
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './SelectMenu.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

/**
 * 드랍 메뉴의 팝업 영역에 쓰이는 옵션 단일 선택 컴포넌트
 * @param {{ optionList: [{ name: string, iconPath: string }] }}
 * @component
 * @example
 *
 * const optionList = [
 *  { name: 'Gallery', selected: true },
 *  { name: 'Table', selected: false },
 * ]
 *
 * return (
 *  <SelectMenu optionList={optionList} />
 * );
 *
 *
 * -
 */
function SelectMenu({ optionList, onChange = noop }) {
  const { t } = useTranslation();
  return (
    <ul className={cx('option-list')}>
      {optionList.map(({ name, iconPath, disable }, key) => (
        <li
          className={cx('option', disable && 'disable')}
          key={key}
          onClick={() => {
            if (!disable) onChange(key);
          }}
        >
          {iconPath && <img className={cx('icon')} src={iconPath} alt='' />}
          {name && <span className={cx('text')}>{t(name)}</span>}
        </li>
      ))}
    </ul>
  );
}

export default SelectMenu;
