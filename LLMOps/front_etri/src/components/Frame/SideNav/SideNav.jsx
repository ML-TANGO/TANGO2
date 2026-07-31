import { useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { useDispatch, useSelector } from 'react-redux';

// Actions
import { closeNav, openNav } from '@src/store/modules/nav';

// Components
import AdminNav from './AdminNav';

// import UserNav from './UserNav';

// CSS Module
import classNames from 'classnames/bind';
import style from './SideNav.module.scss';

const cx = classNames.bind(style);

/**
 * 사이드 네비게이션 컴포넌트
 * @returns {JSX.Element}
 * @component
 * @example
 * return (
 *  <SideNav />
 * )
 *
 *
 * -
 */
function SideNav() {
  // 컴포넌트 상태
  const { nav, auth } = useSelector((state) => ({
    nav: state.nav,
    auth: state.auth,
  }));
  const { isExpand } = nav;
  const { type } = auth;

  const navRef = useRef();

  // Redux hooks
  const dispatch = useDispatch();

  // Events
  const sideNavExpandHadler = () => {
    if (isExpand) dispatch(closeNav());
    else dispatch(openNav());
  };

  useEffect(() => {
    const handleClick = (e) => {
      if (
        navRef.current &&
        !ReactDOM.findDOMNode(navRef.current).contains(e.target) &&
        !e.target.closest('#side-menu-btn')
      ) {
        if (window.innerWidth < 1024) {
          dispatch(closeNav());
        }
      }
    };
    document.addEventListener('click', handleClick, false);
    return () => {
      // cleanup
      document.removeEventListener('click', handleClick, false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      id='SideNav'
      className={cx(
        'gnb',
        isExpand ? 'expand' : 'hide',
        type === 'USER' ? 'user' : 'admin',
      )}
      ref={navRef}
    >
      <div className={cx('nav')}>
        {type === 'ADMIN' && <AdminNav isExpand={isExpand} />}
      </div>
      <div className={cx('nav-footer')}></div>
      <div
        className={cx('fold-box', isExpand && 'open')}
        onClick={() => {
          sideNavExpandHadler();
        }}
      ></div>
    </div>
  );
}

export default SideNav;
