import { useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';

// CSS Module
import classNames from 'classnames/bind';
import style from './Popup.module.scss';

const cx = classNames.bind(style);

/**
 *
 * @param {function} popupHandler 팝업 핸들러 함수
 * @param {JSX.Element} children 자식 컴포넌트
 * @param {string} position 버튼 기준 left | right
 * @component
 * @example
 *
 * const popupHandler = (flag) => {
 *  if (flag === true || flag === false) {
 *    setIsOpen(flag);
 *   } else {
 *     setIsOpen(!isOpen);
 *   }
 * };
 *
 * return (
 *   <Popup popupHandler={popupHandler}>
 *     popup
 *   </Popup>
 * );
 * -
 */
function Popup({ popupHandler, children, position }) {
  const popup = useRef(null);

  useEffect(() => {
    const handleClick = (e) => {
      if (
        popup.current &&
        !ReactDOM.findDOMNode(popup.current).contains(e.target)
      ) {
        popupHandler();
      }
    };
    document.addEventListener('click', handleClick, false);
    return () => {
      document.removeEventListener('click', handleClick, false);
    };
  }, [popupHandler]);
  return (
    <div className={cx('popup-container', position)} ref={popup}>
      {children}
    </div>
  );
}

export default Popup;
