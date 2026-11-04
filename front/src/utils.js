import crypto from 'crypto-js';
import dayjs from 'dayjs';
// export pdf
import html2canvas from 'html2canvas';
// i18n
import i18n from 'i18next';
import jsPdf from 'jspdf';

import { toast } from '@src/components/Toast';

import { expireToken } from '@src/store/modules/auth';

import storeObj from './store/store';

/**
 * 객체 깊은 복사
 *
 * @param {object} obj 복사할 객체
 */
export const deepCopy = (obj) => {
  return JSON.parse(JSON.stringify(obj));
};

/**
 * 문자열 첫번째 글자 대문자로 변경
 *
 * @param {string} s 변경할 문자열
 */
export const capitalizeFirstLetter = (s) => {
  return !s || typeof s !== 'string' || s.length <= 0
    ? s
    : s[0].toUpperCase() + s.slice(1);
};

/**
 * 문자열 각 단어 첫번째 글자 모두 대문자로 변경
 *
 * @param {string} s 변경할 문자열
 */
export const capitalizeFirstLetterAllWords = (s) => {
  if (!s || typeof s !== 'string' || s.length <= 0) {
    return s;
  } else {
    const words = s.split(' ');
    for (let i = 0; i < words.length; i++) {
      words[i] = words[i][0].toUpperCase() + words[i].substr(1);
    }
    return words.join(' ');
  }
};

/**
 * 뒤로가기를 통해 이동했을 경우 이전 스크롤 위치로 이동
 */
export const scrollToPrevPosition = (path) => {
  const prevScrollPos = sessionStorage.getItem(`${path}_scroll_pos`);

  window.scrollTo(0, parseInt(prevScrollPos));
  // 현재스크롤 알아내고
  // 클릭했을때 sessionStorage에 저장
  // 페이지에 들어왔을때 비우기
  // sessionStorage.clear();
  // * 비우기

  // const position = sessionStorage.getItem('prev-scroll-pos');
  // const scrollBox = id ? document.getElementById(id) : window;
  // if (position && scrollBox) scrollBox.scrollTop = parseInt(position, 10);
};

Math.easeInOutQuad = (t, b, c, d) => {
  // eslint-disable-next-line no-param-reassign
  t /= d / 2;
  if (t < 1) return (c / 2) * t * t + b;
  // eslint-disable-next-line no-param-reassign
  t -= 1;
  return (-c / 2) * (t * (t - 2) - 1) + b;
};

/**
 * 스크롤 부드럽게 이동
 *
 * @param {object} element
 * @param {number} to
 * @param {number} duration
 */
export const scrollTo = (element, to, duration, isWindow) => {
  const start = element.scrollTop;
  const change = to - start;
  let currentTime = 0;
  const increment = 20;
  const animateScroll = () => {
    currentTime += increment;
    const val = Math.easeInOutQuad(currentTime, start, change, duration);

    if (isWindow) element.scrollTo(0, to);
    else element.scrollTop = val;

    if (currentTime < duration) {
      setTimeout(animateScroll, increment);
    }
  };
  animateScroll();
};

const ENC_KEY = 'robertirenelico!robertirenelico!'; // set random encryption key
const IV = 'robertirenelico!'; // set random initialisation vector
// ENC_KEY and IV can be generated as crypto.randomBytes(32).toString('hex');

/**
 * 암호화
 *
 * @param {string} val 암호화할 문자열
 */
export const encrypt = (val) => {
  /*
  vite 에서는 crypto 가 일렉트론에서의 호환성 문제때문에 사용불가
  crypto js로 변경
  const cipher = crypto.createCipheriv('aes-256-cbc', ENC_KEY, IV);
  let encrypted = cipher.update(val, 'utf8', 'base64');
  cipher += cipher.final('base64');
  return cipher;
  */
  const wordArray = crypto.enc.Utf8.parse(ENC_KEY);
  const iv = crypto.enc.Utf8.parse(IV);

  const cipher = crypto.AES.encrypt(val, wordArray, {
    iv,
    mode: crypto.mode.CBC,
    keySize: 256,
  });
  return cipher.toString();
};

/**
 * 복호화
 *
 * @param {string} encrypted 암호화된 문자열
 */
export const decrypt = (encrypted) => {
  /*
  const decipher = crypto.createDecipheriv('aes-256-cbc', ENC_KEY, IV);
  const decrypted = decipher.update(encrypted, 'base64', 'utf8');
  return decrypted + decipher.final('utf8');
  vite 에서는 crypto 가 일렉트론에서의 호환성 문제때문에 사용불가
  crypto js로 변경
  */

  const wordArray = crypto.enc.Utf8.parse(ENC_KEY);
  const iv = crypto.enc.Utf8.parse(IV);
  const decipher = crypto.AES.decrypt(encrypted, wordArray, {
    iv,
    mode: crypto.mode.CBC,
    keySize: 256,
  });

  return decipher.toString(crypto.enc.Utf8);
};

/**
 * 만료 설정
 */
export const resetSession = () => {
  storeObj.store.dispatch(expireToken());
  sessionStorage.clear();
};

/**
 * 토큰 변경 설정
 *
 * @param {string} token 토큰
 */
export const refreshToken = (token) => {
  sessionStorage.setItem('token', token);
};

/**
 * 숫자에 1000단위 콤마 넣기
 * @param {number} x 숫자
 */
export const numberWithCommas = (x) => {
  if (!x) return '';
  return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
};

/**
 * PDF로 내보내기
 *
 * @param {string} id HTML tag ID
 */
export const exportPdf = (id) => {
  const input = document.getElementById(id);
  if (!id) {
    toast.error('tag id does not exists');
    return;
  }
  html2canvas(input).then((canvas) => {
    const imgData = canvas.toDataURL('image/png');
    const element = document.getElementById(id);
    const positionInfo = element.getBoundingClientRect();
    const divWidth = positionInfo.width;
    const divHeight = positionInfo.height;
    // eslint-disable-next-line new-cap
    const pdf = new jsPdf({
      orientation: 'horizontal',
      unit: 'mm',
      format: [divWidth, divHeight],
    });
    const ratio = divHeight / divWidth;
    const width = pdf.internal.pageSize.getWidth();
    let height = pdf.internal.pageSize.getHeight();
    height = ratio * width;
    pdf.addImage(imgData, 'PNG', 0, 0, width, height);
    pdf.save(`${id}.pdf`);
  });
};

/**
 * 정수 여부 확인
 *
 * @param {*} num int 타입 체크할 숫자
 */
export const intCheck = (num) => {
  return typeof num === 'number' && num % 1 === 0;
};

/**
 * 다양한 데이터 크기를 Bytes로 변환
 * @param {Number} value Bytes로 바꾸고 싶은 값
 * @param {String} unit value의 단위 Bytes | KB | MB | GB | TB | PB | EB | ZB | YB
 * @returns {Number} Bytes
 */
export const convertSizeToBytes = (value, unit) => {
  if (!isNaN(value)) {
    value = parseFloat(value);
    const units = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = units.indexOf(unit);
    return parseFloat(value * Math.pow(1000, i));
  }
  return value;
};

/**
 * 다양한 데이터 크기를 이진 Bytes로 변환
 * @param {Number} value Bytes로 바꾸고 싶은 값
 * @param {String} unit value의 단위 Bytes | KiB | MiB | GiB | TiB | PiB | EiB | ZiB | YiB
 * @returns {Number} Bytes
 */
export const convertSizeToBinaryBytes = (value, unit) => {
  if (!isNaN(value)) {
    value = parseFloat(value);
    const units = [
      'Bytes',
      'KiB',
      'MiB',
      'GiB',
      'TiB',
      'PiB',
      'EiB',
      'ZiB',
      'YiB',
    ];
    const i = units.indexOf(unit);
    return parseFloat(value * Math.pow(1000, i));
  }
  return value;
};

/**
 * 다양한 데이터 크기 변환
 * @param {Number} value 바꾸고 싶은 값
 * @param {String} unit value의 단위 Bytes | KiB | MiB | GiB | TiB | PiB | EiB | ZiB | YiB
 * @returns {Number} Bytes
 */
export const convertSizeTo = (value, unit) => {
  if (!isNaN(value)) {
    value = parseFloat(value);
    const units = [
      'Bytes',
      'KiB',
      'MiB',
      'GiB',
      'TiB',
      'PiB',
      'EiB',
      'ZiB',
      'YiB',
    ];
    const i = units.indexOf(unit);
    return `${parseFloat(value / Math.pow(1000, i)).toFixed(2)} ${units[i]}`;
  }
  return value;
};

/**
 * 데이터 크기 변환 (Bytes to KB/MB/GB/TB/PB/EB/ZB/YB)
 * @param {Number} bytes
 * @returns {string} size+unit(단위) 소수점 두자리까지 표기
 */
export const convertByte = (bytes) => {
  if (bytes === 0 || isNaN(bytes) || bytes < 0) return '0 Bytes';

  const units = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1000));
  return `${parseFloat((bytes / Math.pow(1000, i)).toFixed(2))} ${units[i]}`;
};

/**
 * 데이터 크기 변환 이진방식 (Bytes to KiB/MiB/GiB/TiB/PiB/EiB/ZiB/YiB)
 * @param {Number} bytes
 * @returns {string} size+unit(단위) 소수점 두자리까지 표기
 */
export const convertBinaryByte = (bytes) => {
  if (bytes === 0 || isNaN(bytes)) return '0 Bytes';
  const units = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1000));
  return `${parseFloat((bytes / Math.pow(1000, i)).toFixed(2))} ${units[i]}`;
};

/**
 * 데이터 크기 변환 (Bytes to KB/MB/GB/TB/PB/EB/ZB/YB)
 * @param {Number} bytes
 * @returns {string} size+unit(단위) 소수점 표시 안하고 반올림
 */
export const convertByteFloor = (bytes) => {
  if (bytes === 0 || isNaN(bytes)) return '0 Bytes';
  const units = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1000));
  return `${Math.round(bytes / Math.pow(1000, i))} ${units[i]}`;
};

/**
 * 데이터 크기 변환 (속도)
 * unit: bit => (bps to Kbps/Mbps/Gbps/Tbps/Pbps/Ebps/Zbps/Ybps)
 *       byte => (Bps to KBps/MBps/GBps/TBps/PBps/EBps/ZBps/YBps)
 * @param {Number} bps
 * @param {string} unit byte | bit(default)
 * @returns {string} size+unit(단위) 소수점 두자리까지 표기
 */
export const convertBps = (bps, unit = 'bit') => {
  let units = [
    'bps',
    'Kbps',
    'Mbps',
    'Gbps',
    'Tbps',
    'Pbps',
    'Ebps',
    'Zbps',
    'Ybps',
  ];
  if (unit.toLowerCase() === 'byte') {
    units = [
      'Bps',
      'KBps',
      'MBps',
      'GBps',
      'TBps',
      'PBps',
      'EBps',
      'ZBps',
      'YBps',
    ];
  }
  if (bps === 0 || isNaN(bps)) return '0 bps';
  const i = Math.floor(Math.log(bps) / Math.log(1000));
  return `${parseFloat((bps / Math.pow(1000, i)).toFixed(2))} ${units[i]}`;
};

/**
 * 오름차순 정렬
 * @param {Array} arr
 * @param {string} target
 * @returns {Array}
 */
export const sortAscending = (arr, target) => {
  return arr.sort((a, b) => {
    return a[target] - b[target];
  });
};

/**
 * 내림차순 정렬
 * @param {Array} arr
 * @param {string} target
 * @returns {Array}
 */
export const sortDescending = (arr, target) => {
  return arr.sort((a, b) => {
    return b[target] - a[target];
  });
};

/**
 * 빈 객체 검사
 * @param {*} param
 * @returns
 */
export function isEmptyObject(param) {
  return Object.keys(param).length === 0 && param.constructor === Object;
}

/**
 * 에러 토스트 메시지 생성
 * @param {object} error
 * @param {string} message
 * @returns
 *
 * example
 * error: {
 *    code: '001',
 *    location: 'datasets',
 *    options: {name: 'irene-test'},
 *  }
 * return toast.error(i18n.t('datasets.001.error.message', { name: 'irene-test' }));
 */
export function errorToastMessage(error, message) {
  if (error?.code && error?.location) {
    const { code, location } = error;
    // 메시지 안에 변수 있는 경우
    if (error?.options) {
      return toast.error(
        i18n.t(`${location}.${code}.error.message`, error.options),
      );
    }
    return toast.error(i18n.t(`${location}.${code}.error.message`));
  }
  // 기존 코드 대응
  if (message) {
    return toast.error(message);
  }
  // default message
  return toast.error(i18n.t('public.000.error.message'));
}

export function errorReturnMessage(error, message) {
  if (error?.code && error?.location) {
    const { code, location } = error;
    // 메시지 안에 변수 있는 경우
    if (error?.options) {
      return i18n.t(`${location}.${code}.error.message`, error.options);
    }
    return i18n.t(`${location}.${code}.error.message`);
  }
  // 기존 코드 대응
  if (message) return message;
  // default message
  return i18n.t('public.000.error.message');
}

/**
 * 성공 토스트 메시지 생성
 * @param {object} success
 * @param {string} message
 * @returns
 */
export function successToastMessage(success, message) {
  if (success?.code && success?.location) {
    const { code, location } = success;
    // 메시지 안에 변수 있는 경우
    if (success?.options) {
      return toast.success(
        i18n.t(`${location}.${code}.success.message`, success.options),
      );
    }
    return toast.success(i18n.t(`${location}.${code}.success.message`));
  }
  // 기존 코드 대응
  if (message) {
    return toast.success(message);
  }
  // default message
  return toast.success(i18n.t('public.000.success.message'));
}

/**
 * 기본 성공 토스트 메시지
 * @param {string} type
 *  create | update | delete | upload | download |
 *  stop | run | clone | change | attach | detach | sync
 * @returns toast.success(i18n.t(`public.000.${type}.success.message`))
 */
export function defaultSuccessToastMessage(type) {
  return toast.success(i18n.t(`public.000.${type}.success.message`));
}

/**
 * 클립보드에 저장
 * @param {string} val 클립보드에 복사할 텍스트
 */
export const copyToClipboard = (val) => {
  const t = document.createElement('textarea');
  document.body.appendChild(t);
  t.value = val;
  t.select();
  document.execCommand('copy');
  document.body.removeChild(t);
};

export const copyToClipboardWithToast = (context) => {
  try {
    copyToClipboard(context);
    toast.success('copy success');
  } catch (error) {
    toast.error('copy fail');
  }
};

/**
 * 포탈 페이지로 이동
 */
export const redirectToPortal = () => {
  // const currentLoc = window.location.href.replace('https://', '');
  const currentLoc = 'flightbase.acryl.ai';
  window.location.href = `${
    import.meta.env.VITE_REACT_APP_INTEGRATION_API_HOST
  }member/login?callbackUrl=${currentLoc}`;
};

/**
 * 초를 받아서 시간으로 변경하는 함수
 * @param {number} seconds
 * @returns
 */

export function formatTime(seconds, t) {
  if (typeof seconds !== 'number') {
    return t('calculating.label');
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  const hoursString = hours > 0 ? `${hours}${t('time.label')}` : '';
  const minutesString = minutes > 0 ? `${minutes}${t('minute.label')}` : '';
  const secondsString =
    remainingSeconds > 0 ? `${remainingSeconds}${t('second.label')}` : '';

  return `${hoursString} ${minutesString} ${secondsString}`.trim();
}

/**
 * 주기적 함수 실행
 * @param {() => boolean} _f - 주기적으로 실행할 함수(boolean 값을 리턴하며 true면 )
 * @param {number} _t - 딜레이 시간
 * @returns {
 *  start: () => {},
 *  stop: () => {},
 *  setFunc: () => {},
 *  setDelay: () => {},
 *  setExcutionCallback: (isFirst: boolean) => {},
 * }
 *
 * @example
 * const instance = infiniteCall();
 *
 * const func = () => {};
 *
 * // 호출 함수 설정
 * instance.setFunc(func);
 *
 * // 딜레이 시간 설정
 * instance.setDelay(2000);
 *
 * // 함수 호출 후 실행되는 함수 설정
 * instance.setExcutionCallback((isFirst) => {
 *   // true면 인스턴스 생성 후 첫 호출
 *   console.log(isFirst);
 * });
 *
 * // 함수 호출 시작
 * instance.start();
 *
 * // 5초 뒤에 정지
 * setTimeout(() => { instance.stop(); }, 2000);
 *
 */
export function infiniteExcute(_f = () => false, _t = 1000) {
  let f = _f;
  let t = _t;
  let status = 'STOP';
  let isFirstExcution = true;
  let excutionCallback = () => {};
  const timer = (ms) => new Promise((res) => setTimeout(res, ms));

  /**
   * 딜레이 시간 setter 함수
   * @param {number} delay 딜레이 시간
   */
  function setDelay(delay) {
    t = delay;
  }

  /**
   * 주기적으로 호출할 함수 setter 함수 (boolean 값을 리턴하며 false면 주기 호출 정지)
   * @param {() => boolean} func 주기적으로 호출할 함수
   */
  function setFunc(func) {
    f = func;
  }

  function setExcutionCallback(func) {
    excutionCallback = func;
  }

  /**
   * 함수 주기 호출 시작
   *
   * setDelay함수를 통해 설정(setDelay 함수로 설정을 안할 경우 1초 마다)
   *
   * 한 시간 간격으로 setFunc을 통해 설정한 함수를 호출
   */
  async function start() {
    if (status === 'RUNNING') {
      // eslint-disable-next-line no-console
      return;
    }

    status = 'RUNNING';
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (status === 'STOP') break;

      // eslint-disable-next-line no-await-in-loop
      const result = await f();
      excutionCallback(isFirstExcution);
      isFirstExcution = false;

      // eslint-disable-next-line no-await-in-loop
      await timer(t);
      if (status === 'STOP') break;

      if (!result) {
        status = 'STOP';
        break;
      }
    }
  }

  /**
   * 함수 주기 호출 정지
   *
   * 주시적으로 실행 중이던 함수 호출 정지
   */
  function stop() {
    status = 'STOP';
  }

  return {
    start,
    stop,
    setFunc,
    setDelay,
    setExcutionCallback,
  };
}

export const getRandomColor = () =>
  `#${Math.floor(Math.random() * 16777215).toString(16)}`;

/**
 * CamelCase로 변경
 *
 * @param {string} str
 * @returns
 */
export const toCamelCase = (str) => {
  return str
    .toLowerCase()
    .replace(/[^a-zA-Z0-9]+(.)/g, (m, chr) => chr.toUpperCase());
};

/**
 * 배열을 translation string으로 반환
 * @param {string | string[]} value
 * @param {i18n.TFunction<'translation'>} t
 * @returns {string}
 */
export const arrayToTranslationString = (value, t) => {
  if (!value) return '';
  if (Array.isArray(value)) {
    let makeStr = '';
    value.forEach((val) => {
      makeStr = `${makeStr}${t ? t(val) : val}`;
    });
    return makeStr;
  }

  return t ? t(value) : value;
};

/**
 * minute정보 -> 경과 시간 계산
 * @param {number} minute
 * @returns {string}
 */
export const calcBeforeDateTime = (minute) => {
  let unit = '';
  let beforeTime = 0;
  if (minute === 0) {
    unit = 'justMoment';
  } else if (minute < 60) {
    unit = 'minute';
    beforeTime = minute;
  } else if (minute < 60 * 24) {
    unit = 'hour';
    beforeTime = Math.round(minute * 0.016);
  } else {
    unit = 'day';
    beforeTime = Math.round(minute * 0.00069);
  }

  return {
    unit,
    beforeTime,
  };
};

/**
 * 초를 s또는 ms으로 표시
 * @param {number} time
 * @returns {string}
 */
export const formatSecondsTime = (time) => {
  if (time >= 1) {
    return `${parseFloat(time.toFixed(3)).toString()}s`;
  }
  return `${parseFloat((time * 1000).toFixed(3)).toString()}ms`;
};

export const theme = {
  PRIMARY_THEME: 'jp-primary',
  DARK_THEME: 'jp-dark',
};

export const bytesToGB = (bytes) => {
  const bytesPerGB = 1073741824;
  return Math.ceil(bytes / bytesPerGB);
};

export const getdivisorArr = (n) => {
  let divisorArr = [];
  for (let i = 1; i <= Math.sqrt(n); i++) {
    if (n % i === 0) {
      divisorArr.push(i);
      if (i !== n / i) {
        divisorArr.push(n / i);
      }
    }
  }
  return divisorArr.sort((a, b) => a - b);
};

export const extractPath = (path) => {
  console.log('-- > ', path);
  if (path === '/' || !path) return null;

  if (path.length > 1 && path[0] === '/') {
    return path.slice(1);
  }

  return path;
};

const apiErrorMsg_fiveTimes =
  'The API failed 5 times. The API will no longer be requested.';
export const executeWithLogging = async (fn) => {
  try {
    await fn();
  } catch (error) {
    logToSnapErrors(error);
  }
};

export const logToSnapErrors = (error) => {
  console.error('[ERROR MESSAGE] ', error.message);
  console.error('[ERROR STACK] ', error.stack);
  toast.error(error.message);
};

export const calIsIntervalErrorToast = (errorCount) => {
  if (errorCount > 5) return true;
  if (errorCount === 5) toast.error(apiErrorMsg_fiveTimes);
  return false;
};

// ** 갯수를 업데이트 해주는 함수 **
export const countUpdater = (count, eas, ea) => {
  if (count > 1) {
    return `${count} ${eas}`;
  }

  return `${count} ${ea}`;
};

export const getFormattedDate = (date) => {
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const day = date.getDate().toString().padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const getDateRange = () => {
  const currentDate = new Date();
  const startDate = new Date(
    currentDate.getFullYear(),
    currentDate.getMonth(),
    1,
  );
  const endDate = new Date(
    currentDate.getFullYear(),
    currentDate.getMonth() + 1,
    0,
  );

  return {
    startDate: `${getFormattedDate(startDate)} 00:00:00`,
    endDate: `${getFormattedDate(endDate)} 23:59:59`,
  };
};

// mail
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const isMailValidate = (mail) => {
  return emailRegex.test(mail);
};

export const convertMBtoGB = (mb) => {
  if (typeof mb !== 'number' || mb < 0) {
    throw new Error('Input must be a non-negative number');
  }
  const gb = mb / 1000;
  return gb;
};

export const handleMoveToScroll = (id, behavior) => {
  const element = document.getElementById(id);
  if (element) {
    if (behavior) {
      element.scrollIntoView({ behavior, block: 'nearest' });
      return;
    }
    element.scrollIntoView();
  }
};

export const calIsCheckDimensionalArr = (arr) => {
  if (!Array.isArray(arr)) return false;
  if (arr.length === 0) return false;
  if (!Array.isArray(arr[0])) return false;

  return true;
};

const options = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false, // 24시간 형식
  timeZone: 'Asia/Seoul', // 한국 시간대 설정
};

/**
 * 주어진 초(소수점 가능)를 D, H, M, S 형태로 변환해 문자열로 반환
 * @param {number} totalSeconds - 예: 1244124.34241
 * @returns {string} 예: "14D 9H 35M 24S"
 */
export function formatSecondsToDHMS(totalSeconds) {
  // 소수점 이하 버리기
  const intSeconds = Math.floor(totalSeconds);

  // 일(D), 시(H), 분(M), 초(S) 추출
  const days = Math.floor(intSeconds / (60 * 60 * 24));
  const remainderAfterDays = intSeconds % (60 * 60 * 24);

  const hours = Math.floor(remainderAfterDays / (60 * 60));
  const remainderAfterHours = remainderAfterDays % (60 * 60);

  const minutes = Math.floor(remainderAfterHours / 60);
  const seconds = remainderAfterHours % 60;

  // 문자열 생성 (D/H/M/S 중 0인 값은 표시 여부를 상황에 맞게 결정 가능)
  let result = '';

  if (days > 0) {
    result += `${days}D `;
  }
  if (days > 0 || hours > 0) {
    result += `${hours}H `;
  }
  if (days > 0 || hours > 0 || minutes > 0) {
    result += `${minutes}M `;
  }
  // 초는 항상 표시
  result += `${seconds}S`;

  return result.trim(); // 맨 뒤 공백 제거
}

/**
 * 주어진 날짜/시간 문자열 예: "2025-01-06 12:53:20"
 * 현재 시각의 차이를 D, H, M, S 형태로 반환 즉, 경과시간
 *
 * @param {string} datetimeStr - "YYYY-MM-DD HH:mm:ss" 형식의 날짜/시간 문자열
 * @returns {string} 경과 시간(예: "1D 3H 20M 5S")
 */
export function getElapsedTime(datetimeStr) {
  if (!datetimeStr) return null;
  // 문자열 -> Date 객체로 변환 ("YYYY-MM-DD HH:mm:ss" -> "YYYY-MM-DDTHH:mm:ss")
  const date = new Date(datetimeStr.replace(' ', 'T'));
  const now = new Date();

  // 경과 시간(밀리초) = 현재 시각 - 주어진 시각
  const diffMs = now - date;

  // 만약 주어진 날짜가 미래라면.. '
  if (diffMs < 0) {
    return null;
  }

  // 밀리초 -> 초
  const diffSec = Math.floor(diffMs / 1000);

  // D, H, M, S 계산
  const days = Math.floor(diffSec / (60 * 60 * 24));
  const daysRemainder = diffSec % (60 * 60 * 24);
  const hours = Math.floor(daysRemainder / 3600);
  const hoursRemainder = daysRemainder % 3600;
  const minutes = Math.floor(hoursRemainder / 60);
  const seconds = hoursRemainder % 60;

  // 조건에 따라 문자열 조합
  // 예: D가 0이면 굳이 "0D"를 표시하지 않고 H부터 표시하는 등
  let result = '';

  if (days > 0) {
    result += `${days} d `;
  }
  if (days > 0 || hours > 0) {
    result += `${hours} h `;
  }
  if (days > 0 || hours > 0 || minutes > 0) {
    result += `${minutes} m `;
  }
  // 초는 무조건 표시
  result += `${seconds} s`;

  return result.trim();
}

/**
 * 주어진 날짜/시간 문자열에 9시간을 더하는 함수
 * @param {string} datetime - "YYYY-MM-DD HH:mm:ss" 형식의 날짜/시간 문자열
 * @returns {string} - 9시간이 더해진 "YYYY-MM-DD HH:mm:ss" 형식의 문자열
 */
export function addNineHours(datetime) {
  if (!datetime) {
    return null;
  }

  // 문자열을 Date 객체로 변환
  const date = new Date(datetime.replace(' ', 'T')); // 공백을 T로 변환해 ISO 형식으로 파싱

  if (isNaN(date.getTime())) {
    // 유효하지 않은 날짜
    return null;
  }

  // 9시간(9 * 60 * 60 * 1000 밀리초)을 더함
  date.setTime(date.getTime() + 9 * 60 * 60 * 1000);

  // 결과를 "YYYY-MM-DD HH:mm:ss" 형식으로 반환
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, '0'); // 월(0부터 시작하므로 +1)
  const dd = String(date.getDate()).padStart(2, '0');
  const hh = String(date.getHours()).padStart(2, '0');
  const mi = String(date.getMinutes()).padStart(2, '0');
  const ss = String(date.getSeconds()).padStart(2, '0');

  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
}

function calculateTimeDifference(date1, date2) {
  const startDate = new Date(date1);
  const endDate = new Date(date2);

  let diffInMs = Math.abs(endDate - startDate);

  const days = Math.floor(diffInMs / (1000 * 60 * 60 * 24));
  diffInMs -= days * (1000 * 60 * 60 * 24);

  const hours = Math.floor(diffInMs / (1000 * 60 * 60));
  diffInMs -= hours * (1000 * 60 * 60);

  const minutes = Math.floor(diffInMs / (1000 * 60));
  diffInMs -= minutes * (1000 * 60);

  const seconds = Math.floor(diffInMs / 1000);

  return `${days} d ${hours} h ${minutes} m ${seconds} s`;
}

export const calRecordTime = (startDateTime, endDateTime) => {
  if (!startDateTime) return '-';

  if (endDateTime) {
    const diffRecordTime = calculateTimeDifference(startDateTime, endDateTime);
    return diffRecordTime;
  }

  const timeToDate = new Date(startDateTime);

  const krStartDateTimeFormatted = new Intl.DateTimeFormat(
    'ko-KR',
    options,
  ).format(timeToDate);

  const offset = 1000 * 60 * 60 * 9; // 9시간 밀리세컨트 값
  const targetDate = new Date(krStartDateTimeFormatted);

  const currentDate = new Date();
  const elapsedTime = currentDate - targetDate - offset;

  const seconds = Math.floor(elapsedTime / 1000); // 초 단위
  const minutes = Math.floor(seconds / 60); // 분 단위
  const hours = Math.floor(minutes / 60); // 시간 단위
  const days = Math.floor(hours / 24); // 일 단위

  return `${days} d ${hours % 24} h ${minutes % 60} m ${seconds % 60} s`;
};

export function calConvertMinutes(minutes) {
  const hours = Math.floor(minutes / 60); // 시간을 계산 (60분 단위로 나누기)
  const remainingMinutes = minutes % 60; // 남은 분 계산 (60으로 나눈 나머지)

  return `${hours} h ${remainingMinutes} m`;
}

export const calFormatSecondToTime = (seconds) => {
  const days = Math.floor(seconds / (60 * 60 * 24));
  seconds -= days * (60 * 60 * 24);

  const hours = Math.floor(seconds / (60 * 60));
  seconds -= hours * (60 * 60);

  const minutes = Math.floor(seconds / 60);
  seconds -= minutes * 60;

  return `${days} d ${hours} h ${minutes} m ${Math.floor(seconds)} s`;
};

export const calCurrentTime = () => {
  const now = new Date();

  const formattedDate =
    now.getFullYear() +
    '-' +
    String(now.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(now.getDate()).padStart(2, '0') +
    ' ' +
    String(now.getHours()).padStart(2, '0') +
    ':' +
    String(now.getMinutes()).padStart(2, '0') +
    ':' +
    String(now.getSeconds()).padStart(2, '0');

  return formattedDate;
};

export function calSecondDifference(time1, time2) {
  // 두 시간 문자열을 Date 객체로 변환
  const date1 = new Date(time1);
  const date2 = new Date(time2);

  const diffInMilliseconds = Math.abs(date2 - date1);
  const diffInSeconds = diffInMilliseconds / 1000;

  return diffInSeconds;
}

export function calPlusNineHours(date) {
  const dateFormat = new Date(date);
  let plusDate = dayjs(dateFormat).add(9, 'hour');
  return plusDate.format('YYYY-MM-DD HH:mm:ss');
}
