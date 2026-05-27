import { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import Cookies from 'universal-cookie';
import queryString from 'query-string';

// Components
import Loading from '@src/components/atoms/loading/Loading';

// Actions
import { loginRequest } from '@src/store/modules/auth';

// Utils
import { redirectToPortal } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './LoadingForIntegrationLogin.module.scss';
const cx = classNames.bind(style);

// 통합 모드에서 어드민 페이지로 접근하기 위해
// 쿼리 파라미터로 isAdmin=true로 보내면 로그인 페이지 접근 가능
const { isAdmin: admin } = queryString.parse(window.location.search);
const isAdmin = admin === 'true';

const cookies = new Cookies();

const MODE = import.meta.env.VITE_REACT_APP_MODE;

/**
 * 통합을 통해 로그인한 경우 쿠키의 access_token으로 로그인 처리하는 컴포넌트
 * 로그인 시도 중에 로딩 화면 제공
 * 성공: 유저 화면으로 이동
 * 실패: 통합페이지로 리다이렉트
 * @component
 * @example
 *
 * return (
 *  <LoadingForintegrationLogin>
 *    { children }
 *  </LoadingForintegrationLogin>
 * )
 */
function LoadingForIntegrationLogin({ children }) {
  const { loading } = useSelector((state) => state.auth);
  // react-redux hooks
  const dispatch = useDispatch();

  useEffect(() => {
    // 통합 모드 and 어드민 페이지 접근을 위한 로그인 페이지가 아닌 경우
    if (MODE === 'INTEGRATION' && !isAdmin) {
      // access_token 통합 로그인을 위한 토큰 값
      const accessToken = cookies.get('access_token');
      const token = sessionStorage.getItem('token');
      const userName = sessionStorage.getItem('user_name');
      const loginedSession = sessionStorage.getItem('loginedSession');

      if (!accessToken) {
        // access_token이 없는 경우 통합 포탈 페이지로 리다이렉트
        redirectToPortal();
      } else if (!token || !userName || !loginedSession) {
        // access_token이 존재하고 세션스토리지에 token, userName, loginedSession 중 하나라도 없을 때 로그인 시도
        dispatch(loginRequest());
      }
    }
  }, [dispatch]);

  if (MODE !== 'INTEGRATION' || isAdmin) return children;

  if (!loading) return children;

  return (
    <div className={cx('outer-box')}>
      <div className={cx('center-box')}>
        <Loading customStyle={{ width: '90px', height: '76px' }} />
        <p className={cx('text')}>
          지금 조나단 플랫폼으로 이동 중입니다.
          <br />
          잠시만 기다려주세요.
          <br />
          <br />
          We're moving to the Jonathan platform now.
          <br />
          Please wait a moment.
        </p>
      </div>
      <img
        className={cx('jf-footer-logo')}
        src='/images/logo/BI_Jonathan.svg'
        alt='JONATHAN logo'
        width='278'
      />
    </div>
  );
}

export default LoadingForIntegrationLogin;
