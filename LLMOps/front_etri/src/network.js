// Response Message
import { MSG } from '@src/msg';
import axios from 'axios';
import i18n from 'i18next';
import Cookies from 'universal-cookie';
import { getMockResponse } from './mockData';

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
const API_HOST = API_HOST_ENV
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const INTEGRATION_API_HOST = import.meta.env
  .VITE_REACT_APP_INTEGRATION_API_HOST;

export const STATUS_FAIL = 'STATUS_FAIL';
export const STATUS_SUCCESS = 'STATUS_SUCCESS';
export const STATUS_INTERNAL_SERVER_ERROR = 'STATUS_INTERNAL_SERVER_ERROR';

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
    if (import.meta.env.VITE_REACT_APP_MOCK !== 'false') {
      const mockData = getMockResponse(url, method, body, null);
      await new Promise(resolve => setTimeout(resolve, 50));
      return {
        data: mockData,
        headers: { token: 'dummy-token' }
      };
    }
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
    ).catch(() => {
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
      toast.error(i18n.t('tokenExpired.message'));
      resetSession();
      if (MODE === 'INTEGRATION')
        window.location.href = `${INTEGRATION_API_HOST}member/logout`;
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
          toast.error(i18n.t('tokenExpired.message'));
          if (MODE === 'INTEGRATION') {
            window.location.href = `${INTEGRATION_API_HOST}member/logout`;
          }
          resetSession();
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
  if (import.meta.env.VITE_REACT_APP_MOCK !== 'false') {
    const mockData = getMockResponse(url, method, null, null);
    const mockRes = {
      status: mockData.status === 1 ? STATUS_SUCCESS : STATUS_FAIL,
      result: mockData.result,
      message: mockData.message,
      error: mockData.error || {},
    };
    await new Promise(resolve => setTimeout(resolve, 50));
    return mockRes;
  }
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
  if (import.meta.env.VITE_REACT_APP_MOCK !== 'false') {
    const mockData = getMockResponse(url, method, body, params);
    const mockRes = {
      status: mockData.status === 1 ? STATUS_SUCCESS : STATUS_FAIL,
      result: mockData.result,
      message: mockData.message,
      error: mockData.error || {},
    };
    await new Promise(resolve => setTimeout(resolve, 50));
    return mockRes;
  }
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
      toast.error(i18n.t('tokenExpired.message'));
      // token expired
      resetSession();
      if (MODE === 'INTEGRATION')
        window.location.href = `${INTEGRATION_API_HOST}member/logout`;
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
    response.status = STATUS_INTERNAL_SERVER_ERROR;
    response.message = MSG.INTERNAL_SERVER_ERROR;
    response.httpStatus = error.response?.status || 0;
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
      toast.error(i18n.t('tokenExpired.message'));
      // token expired
      resetSession();
      if (MODE === 'INTEGRATION')
        window.location.href = `${INTEGRATION_API_HOST}member/logout`;
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

  const res = await axios(reqOpt);

  const headerToken = res.headers?.token;
  const { expired, token: bodyToken } = res.data;
  if (expired) {
    toast.error(i18n.t('tokenExpired.message'));
    resetSession();
    if (MODE === 'INTEGRATION')
      window.location.href = `${INTEGRATION_API_HOST}member/logout`;
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

  const response = await axios.get(`${API_HOST}${url}`, {
    responseType: 'blob',
    headers: {
      'jf-User': userName || 'login',
      'jf-Token': token || 'login',
      'jf-Session': loginedSession || 'login',
    },
  });

  return response.data;
};

export const downloadSshPemBlob = async ({ url }) => {
  const userName = sessionStorage.getItem('user_name');
  const token = sessionStorage.getItem('token');
  const loginedSession = sessionStorage.getItem('loginedSession');
  const cacheBuster = new Date().getTime();

  const response = await axios.get(`${API_HOST}${url}?_=${cacheBuster}`, {
    responseType: 'blob',
    headers: {
      'jf-User': userName || 'login',
      'jf-Token': token || 'login',
      'jf-Session': loginedSession || 'login',
    },
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
