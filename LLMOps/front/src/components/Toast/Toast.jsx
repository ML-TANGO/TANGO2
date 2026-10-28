/* eslint-disable import/no-anonymous-default-export */
import './Toast.scss';
import { toast as _toast } from 'react-toastify';

// 세션 만료 자동 로그아웃 중에는 화면을 떠나는 중이라 개별 요청 실패의 빨간 토스트가
// 의미가 없다 — 만료 시점에 떠 있던 요청 수만큼 쏟아져 안내 토스트를 덮어버린다.
// network.js handleSessionExpired 가 muteErrors() 로 창을 열고, 그동안 error 토스트만
// 삼킨다(success/info/warning 은 그대로).
let errorMuteUntil = 0;

// 이 래퍼를 거치지 않고 react-toastify 의 toast 를 직접 import 하는 파일이 68개 있다.
// ES 모듈은 같은 싱글턴 객체를 공유하므로 그 객체의 error 를 여기서 한 번 감싸두면
// 직접 호출부까지 전부 뮤트가 적용된다 — 68개 파일을 고치지 않는 최소 접근.
// (react-toastify 5.x 의 onChange 는 토스트 단위 정보를 주지 않아 전역 필터가 불가하다.)
const _originalError = _toast.error;
_toast.error = (...args) =>
  Date.now() < errorMuteUntil ? undefined : _originalError.apply(_toast, args);

export default {
  /** 지정 시간(ms) 동안 error 토스트를 삼킨다. 세션 만료 전환 전용. */
  muteErrors: (ms = 5000) => {
    errorMuteUntil = Date.now() + ms;
  },
  success: (title = '', subtitle = '') => {
    _toast.success(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
  info: (title = '', subtitle = '') => {
    _toast.info(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
  error: (title = '', subtitle = '') => {
    // 뮤트는 위에서 감싼 _toast.error 가 일괄 처리한다(직접 호출부와 동일 경로).
    _toast.error(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
  warning: (title = '', subtitle = '') => {
    _toast.warning(
      <>
        <span className='Toastify__toast-body-title'>{title}</span>{' '}
        <span className='Toastify__toast-body-subtitle'>{subtitle}</span>
      </>,
    );
  },
};
