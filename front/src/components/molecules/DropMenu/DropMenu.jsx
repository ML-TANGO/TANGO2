import { useState } from 'react';

// Components
import PopupMenu from './PopupMenu';

// CSS Module
import classNames from 'classnames/bind';
import style from './DropMenu.module.scss';

const cx = classNames.bind(style);

/**
 * 드랍 메뉴 컴포넌트
 * @param {{ btnRender: (isOpen) => JSX.Element, menuRender: () => JSX.Element, align: 'LEFT' | 'RIGHT', customStyle={{}} }}
 * @component
 * @example
 *
 * reutrn (
 *  <DropMenu
 *    btnRender={(isOpen) => <Button>drop button</Button>}
 *    menuRender={() => <Menu />}
 *    align='LEFT'
 *  />
 * );
 */
function DropMenu({
  btnRender,
  menuRender,
  align = 'LEFT',
  isDropUp,
  isScroll = false,
  customStyle,
  maxHeight,
  popMenuCustomStyle = {},
}) {
  const [isOpen, setIsOpen] = useState(false);
  const popupHandler = () => {
    setIsOpen(!isOpen);
  };

  return (
    <div className={cx('drop-menu')} style={customStyle}>
      <div className={cx('btn-wrapper')} onClick={popupHandler}>
        {btnRender(isOpen)}
      </div>
      <div className={cx('menu-wrapper')} style={popMenuCustomStyle}>
        {isOpen && (
          <PopupMenu
            menuRender={menuRender}
            popupHandler={popupHandler}
            align={align}
            isDropUp={isDropUp}
            isOpen={isOpen}
            isScroll={isScroll}
            maxHeight={maxHeight}
          />
        )}
      </div>
    </div>
  );
}

export default DropMenu;
