// actions
import { toast } from 'react-toastify';

import axios from 'axios';
import crypto from 'crypto-js';
import { createAction, handleActions } from 'redux-actions';

import {
  callApi,
  STATUS_FAIL,
  STATUS_INTERNAL_SERVER_ERROR,
  STATUS_SUCCESS,
} from '@src/network';

import { openConfirm } from './confirm';
import { closeDownloadProgress } from './download';
import { closeUploadList } from './upload';

import { encrypt, refreshToken } from '@src/utils';

const MODE = import.meta.env.VITE_REACT_APP_MODE;
const DATASCOPE_URL = import.meta.env.VITE_REACT_APP_DATASCOPE_API_HOST;

// 각 모듈별 함수 구분을 위한 prefix 각 모듈 파일명 + '/' 의 조합으로 구성합니다.
const prefix = 'auth/';

// 액션 타입 선언
const LOGIN_REQUEST = `${prefix}LOGIN_REQUEST`;
const LOGIN_SUCCESS = `${prefix}LOGIN_SUCCESS`;
const LOGIN_FAILURE = `${prefix}LOGIN_FAILURE`;

const LOGOUT_REQUEST = `${prefix}LOGOUT_REQUEST`;
const LOGOUT_SUCCESS = `${prefix}LOGOUT_SUCCESS`;
// const LOGOUT_FAILURE = `${prefix}LOGOUT_FAILURE`;

const RESET_STATE = `${prefix}RESET_STATE`;

const TOKEN_UPDATE = `${prefix}TOKEN_UPDATE`;

// 액션 생성 함수 선언
export const login = createAction(LOGIN_REQUEST);
const loginSuccess = createAction(LOGIN_SUCCESS);
const loginFailure = createAction(LOGIN_FAILURE);

export const logout = createAction(LOGOUT_REQUEST);
const logoutSuccess = createAction(LOGOUT_SUCCESS);
// const logoutFailure = createAction(LOGOUT_FAILURE);

export const resetState = createAction(RESET_STATE);
export const tokenUpdate = createAction(TOKEN_UPDATE);

function forceBlur() {
  // 포커스아웃
  if (document.activeElement) {
    document.activeElement.blur();
  }
}

function commonLoginProcess(dispatch, response, bodyParam, history) {
  const { result, status, message } = response;
  const newState = {
    message,
    status,
  };

  //  API 요청 성공
  if (status === STATUS_SUCCESS) {
    const {
      logined_session: loginedSession,
      user_name: userName,
      admin,
      token,
      photo_url: photoUrl,
      jp_user_name: jpUserName,
      logined,
    } = result;

    // 이미 로그인된 계정
    //  - 강제 로그인 Confirm 팝업 제공
    //  - 확인 클릭 시 loginRequestForce (강제 로그인 함수) 호출
    if (logined) {
      newState.logined = logined;
      forceBlur();

      if (MODE === 'INTEGRATION') {
        // eslint-disable-next-line no-use-before-define
        dispatch(
          loginRequestForce({ ...bodyParam, token, user_name: userName }),
        );
      } else {
        dispatch(
          openConfirm({
            title: '',
            content: 'loginAgain.message',
            testid: 'force-login-modal',
            submit: {
              text: 'confirm.label',
              func: () => {
                // eslint-disable-next-line no-use-before-define
                dispatch(loginRequestForce({ ...bodyParam, token }));
              },
            },
            cancel: {
              text: 'cancel.label',
            },
          }),
        );
      }
      return newState;
    }

    // 로그인 성공
    //  - 로그인 세션 관련 값 세션스토리지에 업데이트
    //  - 스토어에 저장할 유저 정보
    refreshToken(token); // 이부분 추후 통일
    sessionStorage.setItem('user_name', userName);
    sessionStorage.setItem('loginedSession', loginedSession);

    newState.userName = userName;
    newState.type = admin ? 'ADMIN' : 'USER';
    newState.photoUrl = photoUrl || '/images/icon/00-ic-info-user.svg';
    if (jpUserName) newState.jpUserName = jpUserName;
    dispatch(loginSuccess(newState));
    return newState;
  }

  // 통합 모드일 경우 로그인 실패 시 통합 화면으로 리다이렉트
  if (MODE === 'INTEGRATION') {
    // redirectToPortal();
    if (history) history.push('/unknownerror');
  }
  // 로그인 실패
  //  - API 요청은 성공했으나 로그인 요청 실패
  if (status === STATUS_FAIL) {
    const { locked, admin } = result;
    // 계정 잠김 확인
    //  - 계정이 잠겨있는 경우 계정 잠김 알림 팝업 제공
    if (locked) {
      newState.locked = locked;
      dispatch(
        openConfirm({
          title: '',
          content: admin
            ? 'loginLockedAdmin.message'
            : 'loginLockedUser.message',
          submit: { text: 'confirm.label' },
        }),
      );
    }
  }

  // API 요청 실패
  //  - 서버 에러인 경우 toast 에러 메세지 toast 팝업 제공
  //  - api는 성공했으나 작동을 실패한 경우 스토어에 실패 메세지 설정
  //  - 중복 요청 방지 변수(loading) false로 변경
  if (status === STATUS_INTERNAL_SERVER_ERROR) {
    // 서버 에러인 경우 toast 팝업 제공
    toast.error(message);
    dispatch(loginFailure(''));
  } else {
    // api는 성공했으나 작동을 실패한 경우 스토어에 실패 메세지 설정
    dispatch(loginFailure(message));
  }
  return newState;
}

// thunk 함수
//  - loginRequestForce : 강제 로그인 요청 함수
//  - loginRequest : 로그인 요청 함수
//  - logoutRequest : 로그아웃 요청 함수
//  - expireToken : 흐음...

// 강제 로그인 요청 thunk 함수
// - 이미 로그인된 계정이 있는 경우
export const loginRequestForce = (body) => async (dispatch, _, history) => {
  const response = await callApi({
    url: 'login/force',
    method: 'POST',
    body,
  });
  return commonLoginProcess(dispatch, response, {}, history);
};

export const dataScopeEncrpty = (val) => {
  const ENC_KEY = 'ireneaaronlylad!ireneaaronlylad!';
  const IV = 'ireneaaronlylad!';
  const wordArray = crypto.enc.Utf8.parse(ENC_KEY);
  const iv = crypto.enc.Utf8.parse(IV);

  const cipher = crypto.AES.encrypt(val, wordArray, {
    iv,
    mode: crypto.mode.CBC,
    keySize: 256,
  });
  return cipher.toString();
};

export const dataScopeLoginRequest = async (userName, password, dispatch) => {
  const dataScopeReqParam = {
    password,
    provider: 'db',
    refresh: true,
    username: userName,
  };
  try {
    await axios.post(
      `${DATASCOPE_URL}api/v1/security/login`,
      dataScopeReqParam,
    );
    // * 암호화 + encoding
    const encrpyPassword = encodeURIComponent(dataScopeEncrpty(password));
    window.location.href = `${DATASCOPE_URL}login/?username=${userName}&password=${encrpyPassword}`;
  } catch (error) {
    console.log(error);
    dispatch(loginFailure('Please retry login with correct ID and password.'));
  }
};

// 로그인 요청 thunk 함수
export const loginRequest = (body) => async (dispatch) => {
  // loading 값 true로 변경
  //  - 로그인 연속 요청 방지
  // dispatch(login());

  console.log('body : ', body);

  let bodyParam = { ...body };
  if (body) {
    bodyParam = { ...body };
    bodyParam.password = encrypt(body.password);
  }

  const response = await callApi({
    url: 'login',
    method: 'POST',
    body: bodyParam,
  });

  console.log('repsosne : ', response);

  return commonLoginProcess(dispatch, response, bodyParam);
};

// 로그아웃 요청 thunk 함수
export const logoutRequest = () => async (dispatch) => {
  const response = await callApi({
    url: 'logout',
    method: 'post',
  });

  const { status, message, httpStatus } = response;

  if (httpStatus === 403) {
    sessionStorage.clear();
    dispatch(logoutSuccess());
    dispatch(closeUploadList());
    dispatch(closeDownloadProgress());
    return;
  }

  if (status === STATUS_SUCCESS) {
    sessionStorage.clear();
    dispatch(logoutSuccess());
    dispatch(closeUploadList());
    dispatch(closeDownloadProgress());
    if (MODE === 'INTEGRATION') {
      window.location.href = `${
        import.meta.env.VITE_REACT_APP_INTEGRATION_API_HOST
      }member/logout`;
    }
  } else {
    toast.error(message);
  }
};

export const expireToken = () => (dispatch) => {
  sessionStorage.clear();
  dispatch(resetState());
};

export const goToHome =
  (pathname) =>
  (dispatch, getState, { history }) => {
    history.push({
      pathname,
    });
  };

const INIT_STATE = {
  isAuth: false,
  userName: null,
  jpUserName: null,
  type: null,
  photoUrl: '/images/icon/00-ic-info-user.svg',
  token: null,
  loading: true,
  resMessage: '',
};

// reducer - 리듀서 정의
export default handleActions(
  {
    [LOGIN_REQUEST]: (state) => ({ ...state, loading: true }),
    [LOGIN_SUCCESS]: (state, { payload }) => {
      return {
        ...state,
        ...payload,
        loading: false,
        isAuth: true,
        resMessage: '',
      };
    },
    [LOGIN_FAILURE]: (state, { payload: resMessage }) => ({
      ...state,
      loading: false,
      isAuth: false,
      resMessage,
    }),
    [LOGOUT_SUCCESS]: (state) => ({ ...state, isAuth: false }),
    [RESET_STATE]: () => INIT_STATE,
    [TOKEN_UPDATE]: (state, { payload }) => ({ ...state, token: payload }),
  },
  INIT_STATE,
);
