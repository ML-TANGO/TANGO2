import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
// dayjs 플러그인
import utc from 'dayjs/plugin/utc';

import { numberWithCommas } from '@src/utils';

/**
 * dayjs utc 플러그인 설정
 */
dayjs.extend(utc);

/**
 * dayjs duration 플러그인 설정
 */
dayjs.extend(duration);

export const DATE_FORM = 'YYYY-MM-DD';

export const DATE_TIME_FORM = 'YYYY-MM-DD HH:mm:ss';

/**
 * 현재 날짜
 */
export const TODAY = dayjs();

/**
 * 현재날짜
 * 포맷: YYYY.MM.DD
 */
export const today = (form = 'YYYY.MM.DD') => {
  const date = dayjs().local().format(form);
  return date;
};

/**
 * 현재시간
 * 포맷: YYYYMMDD_HHmmss
 */
export const now = () => {
  const datetime = dayjs().local().format('YYYYMMDD_HHmmss');
  return datetime;
};

export const dayjsToString = (date, format = DATE_FORM) => {
  return dayjs(date).format(format);
};

export const dateToDayjsObj = (date) => {
  return dayjs(date);
};

/**
 * 로컬 시간으로 변경
 * 포맷: YYYY-MM-DD HH:mm:ss
 *
 * @param {string} d 변경할 날짜
 * @param {string} format 포멧
 */
export const convertLocalTime = (d, format = 'YYYY-MM-DD HH:mm:ss') => {
  const date = dayjs.utc(d).toDate();
  const local = dayjs(date).local().format(format);
  return local;
};

/**
 * 날짜 dayjs object로 변경
 * @param {string} d 변경할 날짜
 * @returns
 */
export const convertLocalTimeObj = (d) => {
  const date = dayjs.utc(d).toDate();
  const local = dayjs(date).local();
  return local;
};

/**
 *
 * @param {string} d
 * @param {string} format
 */
export const convertUTCTime = (d, format = DATE_TIME_FORM) => {
  const date = dayjs.utc(d).format(format);
  return date;
};

/**
 * 타임스탬프 변경(UTC)
 * @param {number} timeStamp 타임스탬프
 * @param {string} format 변경할 포멧 (YYYY-MM-DD HH:mm:ss)
 */
export const convertTimeStamp = (timeStamp, format = DATE_TIME_FORM) => {
  return dayjs.unix(timeStamp).format(format);
};

/**
 * 타임스탬프 변경(UTC+9)
 * @param {number} timeStamp 타임스탬프
 * @param {string} format 변경할 포멧 (YYYY-MM-DD HH:mm:ss)
 */
export const convertTimeStampUTC9 = (timeStamp, format = DATE_TIME_FORM) => {
  return dayjs.utc(dayjs.unix(timeStamp)).add(9, 'hours').format(format);
};

/**
 * 초를 기간(걸린 시간)으로 변경
 * @param {number} s 초
 * @param {'days' | 'h' | 'm' | 'largeHour'} unit 기간 표시 최종 단위
 * @param {'DD[days] HH[h] mm[m] ss[s]' | 'D:HH:mm:ss'} format 기간 표시 형식
 */
export const convertDuration = (
  s,
  unit,
  format = 'DD[days] HH[h] mm[m] ss[s]',
) => {
  let d = '';

  const duration = dayjs.duration(Math.floor(s) * 1000);

  const [y, mo, da, h, mi, se] = duration.format('Y M D H m s').split(' ');

  const year = Number(y);
  const month = Number(mo);
  const day = Number(da);
  const hour = Number(h);
  const minute = Number(mi);
  const second = Number(se);

  let totalDay = 0;
  if (year !== 0) {
    totalDay = 365 * year;
  }

  if (month !== 0) {
    totalDay = totalDay + 30 * month;
  }

  totalDay += day;

  // day가 2 이상이면 days로 표기되도록 수정
  const isMultipleDay = totalDay > 1 ? 's' : '';

  // days 까지
  if (unit === 'days') {
    return `${numberWithCommas(totalDay)}day${isMultipleDay}`;
  }

  // h 까지
  if (unit === 'h') {
    if (totalDay === 0) {
      return `${hour}h`;
    }
    return `${numberWithCommas(totalDay)}day${isMultipleDay} ${hour}h`;
  }

  // m 까지
  if (unit === 'm') {
    if (totalDay === 0 && hour === 0) {
      return `${minute}m`;
    }
    if (totalDay === 0 && hour !== 0) {
      return `${hour}h ${minute}m`;
    }
    return `${numberWithCommas(
      totalDay,
    )}day${isMultipleDay} ${hour}h ${minute}m`;
  }

  // h 단위
  if (unit === 'largeHour') {
    if (totalDay !== 0) {
      d = `${numberWithCommas(totalDay * 24 + hour)}h`;
    }

    if (minute !== 0) {
      d = `${d === '' ? '' : `${d} `}${minute}m`;
    }

    return `${d === '' ? '' : `${d} `}${second}s`;
  }

  // format에 맞춘 출력
  if (format === 'DD[days] HH[h] mm[m] ss[s]' && totalDay !== 0) {
    d = `${numberWithCommas(totalDay)}day${isMultipleDay}`;
  } else if (format === 'D:HH:mm:ss') {
    d = `${numberWithCommas(totalDay)}:`;
  }

  if (format === 'DD[days] HH[h] mm[m] ss[s]' && hour !== 0) {
    d = `${d === '' ? '' : `${d} `}${hour}h`;
  } else if (format === 'D:HH:mm:ss') {
    d = `${d}${String(hour).length === 1 ? `0${hour}` : hour}:`;
  }

  if (format === 'DD[days] HH[h] mm[m] ss[s]' && minute !== 0) {
    d = `${d === '' ? '' : `${d} `}${minute}m`;
  } else if (format === 'D:HH:mm:ss') {
    d = `${d}${String(minute).length === 1 ? `0${minute}` : minute}:`;
  }

  if (format === 'DD[days] HH[h] mm[m] ss[s]') {
    d = `${d === '' ? '' : `${d} `}${second}s`;
  } else if (format === 'D:HH:mm:ss') {
    d = `${d}${String(second).length === 1 ? `0${second}` : second}`;
  }

  return d;
};

export const convertSeconds = (seconds) => {
  let days = Math.floor(seconds / 86400);
  let hours = Math.floor((seconds % 86400) / 3600);
  let minutes = Math.floor((seconds % 3600) / 60);
  let remainingSeconds = seconds % 60;

  hours = hours < 10 ? '0' + hours : hours;
  minutes = minutes < 10 ? '0' + minutes : minutes;
  remainingSeconds =
    remainingSeconds < 10 ? '0' + remainingSeconds : remainingSeconds;

  if (days < 1) days = '0 days';
  else days = days + ' days';

  return `${days} ${hours}: ${minutes}: ${remainingSeconds}`;
};

/**
 * 기간(걸린 시간) 계산
 *
 * @param {string} sd 시작 시간 (YYYY-MM-DD HH:mm:ss)
 * @param {string} ed 끝난 시간 (YYYY-MM-DD HH:mm:ss)
 * @param {string} unit 기간 표시 최종 단위
 */
export const calcDuration = (sd, ed, unit) => {
  return convertDuration(dayjs(ed).diff(dayjs(sd), 'seconds'), unit);
};

/**
 * 문자열 타입의 날짜를 utc로 변환
 * @param {'YYYY-MM-DD' | 'YYYY-MM-DD HH:mm:ss'} dateTime
 * @param {string} format
 * @returns {string}
 */
export const getUTCTime = (dateTime, format = DATE_TIME_FORM) => {
  const date = dayjs(dateTime).utc().format(format);
  return date;
};

/**
 * 문자열 타입의 날짜를 utc+9로 변환
 * @param {string} dateTime
 * @param {string} format
 * @returns {string}
 */
export const getUTC9Time = (dateTime, format = DATE_TIME_FORM) => {
  const date = dayjs(dateTime).add(9, 'hour').utc().format(format);
  return date;
};

/**
 * 문자열 타입의 날짜를 한국 시간으로 변환
 * @param {string} dateTime
 * @param {string} format
 * @returns {string}
 */
export const getKoreaTime = (dateTime, format = DATE_TIME_FORM) => {
  const date = dayjs(dateTime).utc('z').local().format(format);
  return date;
};

// (1) 새로운 헬퍼 함수 추가
export const convertUTCStartOfDay = (d, format = 'YYYY-MM-DD HH:mm:ss') =>
  dayjs
    .utc(d)
    .startOf('day') // 그 날 00:00:00
    .format(format);

export const convertUTCEndOfDay = (d, format = 'YYYY-MM-DD HH:mm:ss') =>
  dayjs
    .utc(d)
    .endOf('day') // 그 날 23:59:59
    .format(format);
