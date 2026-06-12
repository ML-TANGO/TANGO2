// CSS Module
import classNames from 'classnames/bind';
import style from './BtnMenu.module.scss';
const cx = classNames.bind(style);

/**
 * 드랍 메뉴의 팝업 영역에 쓰이는 버튼 메뉴 컴포넌트
 * @param {{
 *  btnList: [{ name: string, iconPath: string, onClick: Function, testId: string }],
 *  callback: () => {} | null,
 * }}
 * @component
 * @example
 *
 * const btnList = [
 *  { name: 'Stop', iconPath: '/images/icon/00-ic-basic-stop-o.svg', onClick: () => {} },
 *  { name: 'Edit', iconPath: '/images/icon/00-ic-basic-stop-o.svg', onClick: () => {} },
 *  { name: 'Archive', iconPath: '/images/icon/00-ic-basic-stop-o.svg', onClick: () => {} },
 * ]
 *
 * return (
 *  <BtnMenu btnList={btnList} />
 * );
 *
 *
 * -
 */
function BtnMenu({ btnList, callback }) {
  return (
    <ul className={cx('btn-list')}>
      {btnList.map(({ name, iconPath, onClick, disable, testId }, key) => (
        <li
          className={cx('btn', onClick && 'hover', disable && 'disable')}
          key={key}
          data-testid={testId}
          onClick={() => {
            if (disable) return;
            if (onClick) onClick();
            if (callback) callback();
          }}
        >
          {iconPath && <img className={cx('icon')} src={iconPath} alt='' />}
          {name && <span className={cx('text')}>{name}</span>}
        </li>
      ))}
    </ul>
  );
}

export default BtnMenu;
