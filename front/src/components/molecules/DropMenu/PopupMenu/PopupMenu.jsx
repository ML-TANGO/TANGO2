import { useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

// CSS Module
import classNames from 'classnames/bind';
import style from './PopupMenu.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

/**
 * 드랍 메뉴 팝업 컴포넌트
 * @param {{
 *  menuRender: JSX.Element,
 *  popupHandler: Function,
 *  align: 'LEFT' | 'RIGHT',
 *  isOpen: boolean,
 *  isScroll: boolean,
 *  isDropUp: boolean,
 * }}
 * @component
 * @example
 *
 * const popupHandler = () => {};
 *
 *
 * return (
 *  <PopupMenu
 *    menuRender={<Menu />}             // 메뉴 팝업에 들어갈 컴포넌트
 *    popupHandler={popupHandler} // 메뉴 팝업 열고 닫는 이벤트 함수
 *    align='RIGHT'               // 메뉴 팝업의 좌우 정렬 LEFT: 좌측 정렬, RIGHT: 우측 정렬
 *    isDropUp={true}             // 메뉴 팝업의 수직 정렬
 *  />
 * )
 */
function PopupMenu({
  menuRender,
  popupHandler = noop,
  align = 'LEFT',
  isDropUp,
  isOpen,
  isScroll,
  maxHeight = '320px',
}) {
  const popup = useRef(null);

  const styleObj = {
    display: isOpen ? 'block' : 'none',
    overflow: isScroll ? 'auto' : 'visible',
  };
  if (align === 'LEFT') styleObj.left = 0;
  else if (align === 'RIGHT') styleObj.right = 0;
  if (isDropUp) styleObj.bottom = '40px';
  else styleObj.top = '4px';

  const handleClick = (e) => {
    // PopupMenu를 제외한 요소 클릭 시 popupHandler 이벤트 실행
    if (
      popup.current &&
      !ReactDOM.findDOMNode(popup.current).contains(e.target)
    ) {
      popupHandler();
    }
  };

  // 클릭 이벤트 관련 라이프 사이클
  useEffect(() => {
    // 애니메이션
    popup.current.style.maxHeight = '0px';
    popup.current.style.maxHeight = maxHeight;

    // PopupMenu 컴포넌트가 마운트 될 때 documemnt에 팝업 닫기 이벤트 추가
    document.addEventListener('click', handleClick, true);
    return () => {
      // 현재 컴포넌트가 언마운트 되면 handleClick 이벤트 제거
      document.removeEventListener('click', handleClick, false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [popup]);

  return (
    <div className={cx('menu')} style={styleObj} ref={popup}>
      {menuRender(popupHandler)}
    </div>
  );
}

export default PopupMenu;
