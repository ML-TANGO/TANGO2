// Response Message
import { MSG } from '@src/msg';
import axios from 'axios';
import i18n from 'i18next';
import Cookies from 'universal-cookie';

// Components
import { toast } from '@src/components/Toast';

// Actions
import { goToHome } from '@src/store/modules/auth';
import storeObj from '@src/store/store';

// Utils
import { refreshToken, resetSession } from '@src/utils';

axios.defaults.withCredentials = true;
const cookies = new Cookies();

const MODE = import.meta.env.VITE_REACT_APP_MODE;
const API_HOST_ENV = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
export const API_HOST = API_HOST_ENV
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const INTEGRATION_API_HOST = import.meta.env
  .VITE_REACT_APP_INTEGRATION_API_HOST;

export const STATUS_FAIL = 'STATUS_FAIL';
export const STATUS_SUCCESS = 'STATUS_SUCCESS';
export const STATUS_INTERNAL_SERVER_ERROR = 'STATUS_INTERNAL_SERVER_ERROR';

// 세션/토큰 만료 → 자동 로그아웃. 기존엔 빨간 에러 토스트만 띄우고 화면에 머물러
// 불편했음 → 세션 정리 + /login 이동(자동 로그아웃) + 부드러운 안내 토스트로 통일.
// 동시 다발 401 응답에 토스트/리다이렉트가 중복되지 않도록 1회만 처리(잠시 후 해제 → 재로그인 대비).
let sessionExpiredHandled = false;
// export — SSE(EventSource)는 network.js 를 거치지 않아 만료를 스스로 감지할 수 없다.
// utils/sse.js 가 SSE 실패를 분류한 뒤 만료로 판정되면 이 함수를 직접 호출한다.
export const handleSessionExpired = () => {
  if (sessionExpiredHandled) return;
  sessionExpiredHandled = true;
  setTimeout(() => {
    sessionExpiredHandled = false;
  }, 3000);

  resetSession(); // sessionStorage clear + auth 상태 초기화(isAuth=false)

  if (MODE === 'INTEGRATION') {
    // 통합 인증은 통합 로그아웃 엔드포인트가 세션/리다이렉트를 관장.
    window.location.href = `${INTEGRATION_API_HOST}member/logout`;
    return;
  }
  // standalone(TANGO): 부드러운 안내 후 로그인 화면으로 자동 이동(SPA — 토스트 유지).
  // 만료 시점에 떠 있던 다른 요청들도 줄줄이 실패하며 빨간 토스트를 띄운다
  // ('Token expired' 등). 로그인 화면으로 나가는 중이라 무의미하고 안내만 가리므로
  // 잠시 error 토스트를 삼킨다 — 사용자에게는 아래 안내 하나만 보인다.
  toast.muteErrors(5000);
  toast.info(i18n.t('sessionExpired.message'));
  storeObj.store.dispatch(goToHome('/login'));
};

// 만료 신호 판정 —
// 이 플랫폼은 세션 관리를 게이트웨이에 위임했다(fb_user login: login_session 테이블 대신
// Kong session 사용). 전역 session 플러그인(rolling_timeout 1시간)이 만료되면 요청은
// anonymous consumer 로 폴백되고 request-termination 이 **403(HTML)** 으로 끊는다.
// 즉 이 플랫폼의 만료 신호는 401 이 아니라 403 이다 — store/modules/auth.js 의
// logoutRequest 도 같은 이유로 403 을 '이미 만료' 로 처리한다.
// 앱이 직접 내는 403(권한 부족)은 JSONResponse 이므로 Content-Type 으로 구분한다.
const isGatewayTermination = (response) => {
  const headers = response?.headers || {};
  const contentType = headers['content-type'] || headers['Content-Type'] || '';
  return !contentType.includes('application/json');
};

// 로그인 실패도 401 을 쓴다(fb_user login: "Please retry login with correct ID and
// password."). 이를 만료로 오인하면 비밀번호 오타에 만료 안내가 뜬다.
// 로그아웃은 auth.js logoutRequest 가 403 을 이미 처리하므로 중복 안내를 피한다.
const EXPIRY_EXEMPT_URLS = ['login', 'login/force', 'logout'];
const isExpiryExemptUrl = (url) =>
  EXPIRY_EXEMPT_URLS.includes(String(url || '').replace(/^\/+/, ''));

/**
 * 응답이 세션 만료를 뜻하면 자동 로그아웃을 발동한다.
 *
 * @param {Error} error axios 에러
 * @param {string} [url] 요청 URL (인증 엔드포인트 제외 판정용)
 * @returns {boolean} 만료로 판정해 로그아웃을 발동했는지 여부
 */
const handleIfSessionExpired = (error, url) => {
  if (isExpiryExemptUrl(url)) return false;
  const status = error?.response?.status;
  const isExpired =
    status === 401 || (status === 403 && isGatewayTermination(error.response));
  if (isExpired) handleSessionExpired();
  return isExpired;
};

export const network = (() => {
  const accessToken = cookies.get('access_token');

  const callApiWithPromise = async ({
    url,
    method,
    header,
    body,
    responseType,
    onDownloadProgress,
  }) => {
    const user = sessionStorage.getItem('user_name');
    const token = sessionStorage.getItem('token');
    const loginedSession = sessionStorage.getItem('loginedSession');
    const methodLowercase = method.toLowerCase();

    if (
      user === 'demo' &&
      (methodLowercase === 'put' ||
        methodLowercase === 'post' ||
        methodLowercase === 'delete')
    ) {
      toast.info('Permission denied.');
      return new Promise((resolve, reject) => {
        reject();
      });
    }

    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
      'jf-User': !user ? 'login' : user,
      'jf-Token': !token ? 'login' : token,
      'jf-Session': !loginedSession ? 'login' : loginedSession,
    };

    if (MODE === 'INTEGRATION') {
      headers.Authorization = accessToken;
    }

    if (header) {
      const headerKeys = Object.keys(header);
      for (let i = 0; i < headerKeys.length; i += 1) {
        headers[headerKeys[i]] = header[headerKeys[i]];
      }
    }
    const reqOpt = { headers };
    if (responseType) reqOpt.responseType = responseType;
    reqOpt.onDownloadProgress = (progressEvent) => {
      if (onDownloadProgress) {
        onDownloadProgress(
          Math.round((progressEvent.loaded * 100) / progressEvent.total),
        );
      }
    };

    const res = await axios[methodLowercase](
      `${API_HOST}${url}`,
      methodLowercase === 'get' || methodLowercase === 'delete' ? reqOpt : body,
      methodLowercase !== 'get' && methodLowercase !== 'delete' && reqOpt,
    ).catch((error) => {
      // 만료 신호는 원래 200 + body.expired 였다. 게이트웨이가 만료 세션을 끊는 경우엔
      // body 가 HTML 이라 그 검사가 안 걸린다 → 상태코드로 판정한다.
      handleIfSessionExpired(error, url);
      return {
        data: {
          status: 0,
          message: 'Network error',
        },
      };
    });
    const headerToken = res.headers?.token;
    const { expired, token: bodyToken } = res.data;
    if (expired) {
      handleSessionExpired();
      return res;
    }
    if (bodyToken || headerToken) {
      const newToken = bodyToken || headerToken;
      // token update
      refreshToken(newToken);
    }
    if (res.data.redirect === true) {
      storeObj.store.dispatch(goToHome('/user/dashboard'));
      toast.warning(i18n.t('unauthorized.message'));
      return {
        data: {
          status: 0,
          message: 'Network error',
        },
      };
    }
    return res;
  };

  const callServiceApi = async ({ url, method, header, body }) => {
    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
    };
    if (header) {
      const headerKeys = Object.keys(header);
      for (let i = 0; i < headerKeys.length; i += 1) {
        headers[headerKeys[i]] = header[headerKeys[i]];
      }
    }
    const start = new Date();
    const res = await axios[method.toLowerCase()](
      url,
      method.toLowerCase() === 'get' || method.toLowerCase() === 'delete'
        ? { headers }
        : body,
      method.toLowerCase() !== 'get' &&
        method.toLowerCase() !== 'delete' && { headers },
    ).catch((error) => {
      if (!error.response) return { status: -1, message: 'Network error' };
      // 여기서는 만료 판정을 하지 않는다 — callServiceApi 는 플랫폼 API 가 아니라
      // 배포된 모델의 추론 엔드포인트(apiUrl)를 직접 호출하며 플랫폼 세션 헤더도
      // 싣지 않는다. 게시 route 의 key-auth 거부(401/403)를 세션 만료로 오인하면
      // 추론 테스트 중 엉뚱하게 로그아웃된다. 실제 만료는 같은 화면의 다른
      // 플랫폼 API 호출이 잡는다.
      return { status: 0, message: error.response.statusText };
    });
    const elapsedTime = new Date() - start;
    return { ...res, time: elapsedTime };
  };

  const callIntegrationApi = async ({
    url,
    method,
    header,
    body,
    successFunc,
    failFunc,
  }) => {
    // const accessToken = cookies.get('access_token');
    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
      Authorization: accessToken,
    };

    if (header) {
      const headerKeys = Object.keys(header);
      for (let i = 0; i < headerKeys.length; i += 1) {
        headers[headerKeys[i]] = header[headerKeys[i]];
      }
    }

    return axios({
      url: `${INTEGRATION_API_HOST}${url}`,
      method: method.toLowerCase(),
      data: body,
      headers,
    })
      .then((res) => {
        if (res.data.expired) {
          handleSessionExpired();
        }
        if (
          (res.data?.token || res.headers?.token) &&
          !(url === 'login' || url === 'login/force')
        ) {
          refreshToken(res.data?.token || res.headers?.token);
        }
        if (successFunc) successFunc(res);
      })
      .catch((error) => {
        handleIfSessionExpired(error, url);
        if (failFunc) failFunc(error);
      });
  };

  const callMarkerApi = async ({ url, method, header, body }) => {
    const user = sessionStorage.getItem('user_name');
    const token = sessionStorage.getItem('token');

    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
      'jf-User': !user ? 'login' : user,
      'jf-Token': !token ? 'login' : token,
    };

    if (MODE === 'INTEGRATION') headers.Authorization = accessToken;

    if (header) {
      const headerKeys = Object.keys(header);
      for (let i = 0; i < headerKeys.length; i += 1) {
        headers[headerKeys[i]] = header[headerKeys[i]];
      }
    }

    try {
      const res = await axios({
        url: `${
          import.meta.env.VITE_VITE_REACT_APP_MARKER_API_HOST
        }marker-api/${url}`,
        method: method.toLowerCase(),
        data: body,
        headers,
      });

      if (!res || !res.data || !res.data.response) {
        throw new Error('No Response.');
      }

      return res;
    } catch (err) {
      throw err;
    }
  };

  return {
    callApiWithPromise,
    callServiceApi,
    callIntegrationApi,
    callMarkerApi,
  };
})();

// 데이터셋 전용 임시 함수
/**
 * api 호출 함수
 * @param {{
 *  url: string,
 *  method: 'post' | 'put' | 'delete',
 *  header: object,
 *  form: FormData,
 * }} param request pararmeter
 * @returns {{
 *  result: Object,
 *  status: STATUS_SUCCESS | STATUS_INTERNAL_SERVER_ERROR | STATUS_FAIL,
 *  message: string,
 * }} return type
 */
export async function callApiWithForm({
  url,
  method = 'post',
  header = {},
  form,
}) {
  const accessToken = cookies.get('access_token');
  const response = {
    result: {},
    message: '',
    status: STATUS_FAIL,
    error: {},
  };

  const userName = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');

  if (
    userName === 'demo' &&
    (method.toLowerCase() === 'put' ||
      method.toLowerCase() === 'post' ||
      method.toLowerCase() === 'delete')
  ) {
    response.message = 'Permission denied.';
    return response;
  }

  const headers = {
    'content-type': 'multipart/form-data',
    'jf-User': userName || 'login',
    'jf-Token': token || 'login',
    'jf-Session': loginedSession || 'login',
  };

  if (MODE === 'INTEGRATION') {
    headers.Authorization = accessToken;
  }

  if (header) {
    const headerKeys = Object.keys(header);
    for (let i = 0; i < headerKeys.length; i += 1) {
      headers[headerKeys[i]] = header[headerKeys[i]];
    }
  }

  const reqConfig = {
    method,
    url: `${API_HOST}${url}`,
    headers,
    data: form,
  };

  try {
    const res = await axios(reqConfig);
    const { status, message, error } = res.data;

    if (status === 1) {
      response.status = STATUS_SUCCESS;
    } else {
      response.status = STATUS_FAIL;
      response.error = error;
    }

    response.message = message;
    return response;
  } catch (error) {
    response.httpStatus = error.response?.status || 0;
    if (handleIfSessionExpired(error, url)) {
      // 만료는 ISE 가 아니다. 200 + body.expired 경로와 같은 신호를 돌려줘야
      // 호출부가 빨간 'Internal server error' 토스트를 겹쳐 띄우지 않는다.
      response.status = STATUS_FAIL;
      response.message = MSG.TOKEN_EXPIRED;
      return response;
    }
    response.status = STATUS_INTERNAL_SERVER_ERROR;
    response.message = MSG.INTERNAL_SERVER_ERROR;
    return response;
  }
}

/**
 * api 호출 함수
 * @param {{
 *  url: string,
 *  method: 'get' | 'post' | 'put' | 'delete',
 *  header: object,
 *  body: object,
 * }} param request pararmeter
 * @returns {{
 *  result: Object,
 *  status: STATUS_SUCCESS | STATUS_INTERNAL_SERVER_ERROR | STATUS_FAIL,
 *  message: string,
 * }} return type
 */
export async function callApi({
  url,
  method = 'get',
  header = {},
  body,
  params,
  isFormData = false,
  signal = false,
}) {
  const accessToken = cookies.get('access_token');
  const response = {
    result: {},
    message: '',
    status: STATUS_FAIL,
    error: {},
  };

  const userName = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');

  if (
    userName === 'demo' &&
    (method.toLowerCase() === 'put' ||
      method.toLowerCase() === 'post' ||
      method.toLowerCase() === 'delete')
  ) {
    response.message = 'Permission denied.';
    return response;
  }

  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json;charset=UTF-8' }),
    'jf-User': userName || 'login',
    'jf-Token': token || 'login',
    'jf-Session': loginedSession || 'login',
  };

  if (MODE === 'INTEGRATION') {
    headers.Authorization = accessToken;
  }

  if (header) {
    const headerKeys = Object.keys(header);
    for (let i = 0; i < headerKeys.length; i += 1) {
      headers[headerKeys[i]] = header[headerKeys[i]];
    }
  }

  const reqConfig = {
    method,
    url: `${API_HOST}${url}`,
    headers: headers,
    signal,
    // withCredentials: true,
    // timeout: 60000,
    params,
  };

  if (body) reqConfig.data = body;

  try {
    const res = await axios(reqConfig);
    const headerToken = res.headers?.token;
    const {
      expired,
      token: bodyToken,
      result,
      status,
      message,
      locked,
      error,
    } = res.data;

    if (status === 1) {
      response.status = STATUS_SUCCESS;
    } else {
      response.status = STATUS_FAIL;
      response.error = error;
    }

    if (expired) {
      response.status = STATUS_FAIL;
      response.message = MSG.TOKEN_EXPIRED;
      handleSessionExpired();
      return response;
    }
    if (bodyToken || headerToken) {
      const newToken = bodyToken || headerToken;
      // token update
      refreshToken(newToken);
    }

    if (locked) {
      response.status = STATUS_FAIL;
      response.result = { locked };
    } else {
      response.result = result === null || result === undefined ? {} : result;
    }

    response.message = message;

    if (res.data.length) {
      // JOB/HPS 로그 데이터 길이 받아오기 위함
      response.length = res.data.length;
    }

    return response;
  } catch (error) {
    response.httpStatus = error.response?.status || 0;
    // 게이트웨이가 만료 세션을 끊는 경로 — 본문이 HTML 이라 body.expired 검사가
    // 안 걸리므로 여기서 상태코드로 판정한다.
    if (handleIfSessionExpired(error, url)) {
      // 만료는 ISE 가 아니다. 200 + body.expired 경로와 같은 신호를 돌려줘야
      // 호출부가 빨간 'Internal server error' 토스트를 겹쳐 띄우지 않는다.
      response.status = STATUS_FAIL;
      response.message = MSG.TOKEN_EXPIRED;
      return response;
    }
    response.status = STATUS_INTERNAL_SERVER_ERROR;
    response.message = MSG.INTERNAL_SERVER_ERROR;
    return response;
  }
}

/**
 * 파일 업로드 api 호출 함수
 * @param {{
 *   url: string, method: 'get' | 'post' | 'put' | 'delete',
 *   header: { [key: string]: any },
 *   form: FormData,
 *   progressCallback: function
 * }} param request pararmeter
 * @returns {{
 *  result: Object,
 *  status: STATUS_SUCCESS | STATUS_INTERNAL_SERVER_ERROR | STATUS_FAIL,
 *  message: string,
 * }} return type
 */
export async function upload({
  url,
  method = 'get',
  header = {},
  form,
  progressCallback,
}) {
  const accessToken = cookies.get('access_token');
  const response = {
    result: {},
    message: '',
    status: STATUS_FAIL,
    error: {},
  };

  const userName = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');

  if (
    userName === 'demo' &&
    (method.toLowerCase() === 'put' ||
      method.toLowerCase() === 'post' ||
      method.toLowerCase() === 'delete')
  ) {
    response.message = 'Permission denied.';
    return response;
  }

  const headers = {
    'jf-User': userName || 'login',
    'jf-Token': token || 'login',
    'jf-Session': loginedSession || 'login',
  };

  if (MODE === 'INTEGRATION') {
    headers.Authorization = accessToken;
  }

  if (header) {
    const headerKeys = Object.keys(header);
    for (let i = 0; i < headerKeys.length; i += 1) {
      headers[headerKeys[i]] = header[headerKeys[i]];
    }
  }

  const reqConfig = {
    method,
    url: `${API_HOST}${url}`,
    headers,
    data: form,
    onUploadProgress(progressEvent) {
      if (progressCallback) {
        progressCallback(
          Math.round((progressEvent.loaded * 100) / progressEvent.total),
        );
      }
    },
  };

  try {
    const res = await axios(reqConfig);
    const headerToken = res.headers?.token;
    const {
      expired,
      token: bodyToken,
      result,
      status,
      message,
      locked,
      error,
    } = res.data;

    if (status === 1) {
      response.status = STATUS_SUCCESS;
    } else {
      response.status = STATUS_FAIL;
      response.error = error;
    }

    if (expired) {
      response.status = STATUS_FAIL;
      response.message = MSG.TOKEN_EXPIRED;
      handleSessionExpired();
      return response;
    }
    if (bodyToken || headerToken) {
      const newToken = bodyToken || headerToken;
      // token update
      refreshToken(newToken);
    }

    if (locked) {
      response.status = STATUS_FAIL;
      response.result = { locked };
    } else {
      response.result = result || {};
    }

    response.message = message;
    return response;
  } catch (error) {
    response.httpStatus = error.response?.status || 0;
    if (handleIfSessionExpired(error, url)) {
      // 만료는 ISE 가 아니다. 200 + body.expired 경로와 같은 신호를 돌려줘야
      // 호출부가 빨간 'Internal server error' 토스트를 겹쳐 띄우지 않는다.
      response.status = STATUS_FAIL;
      response.message = MSG.TOKEN_EXPIRED;
      return response;
    }
    response.status = STATUS_INTERNAL_SERVER_ERROR;
    response.message = MSG.INTERNAL_SERVER_ERROR;
    return response;
  }
}

export const download = async ({
  url,
  method,
  header,
  responseType,
  onDownloadProgress,
}) => {
  const user = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');
  const methodLowercase = method.toLowerCase();

  if (
    user === 'demo' &&
    (methodLowercase === 'put' ||
      methodLowercase === 'post' ||
      methodLowercase === 'delete')
  ) {
    toast.info('Permission denied.');
    return new Promise((resolve, reject) => {
      reject();
    });
  }

  const headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    'jf-User': !user ? 'login' : user,
    'jf-Token': !token ? 'login' : token,
    'jf-Session': !loginedSession ? 'login' : loginedSession,
  };

  if (MODE === 'INTEGRATION') {
    headers.Authorization = cookies.get('access_token');
  }

  if (header) {
    const headerKeys = Object.keys(header);
    for (let i = 0; i < headerKeys.length; i += 1) {
      headers[headerKeys[i]] = header[headerKeys[i]];
    }
  }

  const reqOpt = {
    headers,
    method,
    url: `${API_HOST}${url}`,
    responseType,
    onDownloadProgress: (progressEvent) => {
      if (onDownloadProgress) {
        onDownloadProgress(
          Math.round((progressEvent.loaded * 100) / progressEvent.total),
        );
      }
    },
  };

  // 다운로드도 만료 대상. 기존 계약(reject 전파)은 그대로 두고 로그아웃만 얹는다.
  const res = await axios(reqOpt).catch((error) => {
    handleIfSessionExpired(error, url);
    throw error;
  });

  const headerToken = res.headers?.token;
  const { expired, token: bodyToken } = res.data;
  if (expired) {
    handleSessionExpired();
    return res;
  }
  if (bodyToken || headerToken) {
    const newToken = bodyToken || headerToken;
    // token update
    refreshToken(newToken);
  }
  if (res.data.redirect === true) {
    storeObj.store.dispatch(goToHome('/user/dashboard'));
    toast.warning(i18n.t('unauthorized.message'));
    return {
      data: {
        status: 0,
        message: 'Network error',
      },
    };
  }
  return res;
};

export const downloadBlob = async ({ url }) => {
  const userName = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');

  const response = await axios
    .get(`${API_HOST}${url}`, {
      responseType: 'blob',
      headers: {
        'jf-User': userName || 'login',
        'jf-Token': token || 'login',
        'jf-Session': loginedSession || 'login',
      },
    })
    .catch((error) => {
      handleIfSessionExpired(error, url);
      throw error;
    });

  return response.data;
};

export const downloadSshPemBlob = async ({ url }) => {
  const userName = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');
  const cacheBuster = new Date().getTime();

  const response = await axios
    .get(`${API_HOST}${url}?_=${cacheBuster}`, {
      responseType: 'blob',
      headers: {
        'jf-User': userName || 'login',
        'jf-Token': token || 'login',
        'jf-Session': loginedSession || 'login',
      },
    })
    .catch((error) => {
      handleIfSessionExpired(error, url);
      throw error;
    });

  return response.data;
};

// 기본 Axios 인스턴스 생성
const axiosInstance = axios.create({
  baseURL: API_HOST,
  headers: {
    'Content-Type': 'application/json;charset=UTF-8',
  },
});

// 파일 업로드 전용 Axios 인스턴스 생성
const uploadAxiosInstance = axios.create({
  baseURL: API_HOST,
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});
