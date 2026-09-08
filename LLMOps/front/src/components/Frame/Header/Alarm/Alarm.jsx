// Image
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { shallowEqual, useSelector } from 'react-redux';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import { callApi, STATUS_SUCCESS } from '@src/network';
import {
  classifySseFailure,
  createSseRetryState,
  SSE_FAILURE,
  SSE_RETRY,
  sseRetryDelay,
} from '@src/utils/sse';

import AlarmDetail from './AlarmDetail';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './Alarm.module.scss';

import AlarmIcon from '@src/static/images/icon/00-ic-alarm-active.svg';

const cx = classNames.bind(style);

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

const Alarm = () => {
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [alarmList, setAlarmList] = useState([]);
  const [alarmCount, setAlarmCount] = useState(0);
  const [isOpen, setOpen] = useState(false);

  const getAlarmList = useCallback(async () => {
    const res = await callApi({
      url: 'notification/recent-history',
      method: 'get',
    });

    const { result, status, message } = res;

    if (status === STATUS_SUCCESS) {
      setAlarmList(result);
      isLoading.current = false;
    } else {
      errorToastMessage(message);
    }
  }, []);

  const doubleRef = useRef(false);
  const handleAlarmToggle = useCallback(() => {
    if (doubleRef.current) return;
    isLoading.current = false;
    doubleRef.current = true;

    setOpen((prev) => {
      const newOpen = !prev;
      if (newOpen) {
        getAlarmList();
      }
      return newOpen;
    });
    setTimeout(() => {
      doubleRef.current = false;
    }, 250);
  }, [getAlarmList]);

  // ** 초기에 alarm 데이터 SSE로 받아옵니다. ALARM 컴포넌트 MEMO 처리 **
  //
  // 재연결 정책은 utils/sse.js 를 따른다(6개 SSE 소비처 공용). 예전엔 이 파일만 정책 밖에
  // 있어서 onerror 마다 무조건 5초 후 재연결을 무한 반복했다 — 세션이 끊긴 뒤 로그인
  // 화면에서도 5초마다 게이트웨이를 계속 두드렸고(실측: /api/notification/sse 403 이 5초
  // 간격으로 수백 건), 만료·권한없음·일시장애를 구분하지 못했다.
  const eventSourceRef = useRef(null);
  // attempt(재시도 횟수)를 컴포넌트 수명에 고정한다. effect 지역변수로 두면 재마운트마다
  // 0 으로 초기화돼 재시도 상한이 무너진다(utils/sse.js 주석 참조).
  const sseRetryRef = useRef(createSseRetryState());
  useEffect(() => {
    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const retry = sseRetryRef.current;
    // 공유 상태의 `notified`(첫 실패 1회만 토스트 안내)는 의도적으로 쓰지 않는다 — 알람은
    // 헤더 배지라 실시간 갱신이 끊겨도 토스트를 띄우지 않는다(useDashboardSse 와 다른 점).
    // ⚠️ 생존 판정은 **effect 지역 플래그**로 한다. 공유 상태의 `alive` 를 effect 재실행마다
    // true 로 되살리면 세대 구분이 안 된다 — userName 이 바뀌는 순간, 이전 effect 의 onerror
    // 가 classifySseFailure 의 await(최대 5초) 안에 있다가 늦게 resolve 되면 되살아난 alive
    // 를 통과해 옛 headers 로 재연결한다(추적 불가한 좀비 EventSource + 타이머).
    // 지역 플래그는 한 번 false 가 되면 그 세대에서 영구 false 라 그 경로가 닫힌다.
    let isCurrent = true;
    // EXPIRED/FATAL 로 확정 중단된 뒤에는 탭 복귀로도 되살리지 않는다(같은 실패 반복 방지).
    let stopped = false;
    let retryTimeout;

    const url = `${API_HOST}notification/sse`;
    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
      'jf-User': userName || 'login',
      'jf-Token': token || 'login',
      'jf-Session': loginedSession || 'login',
      // 통합 인증에서만 붙인다. 예전엔 `MODE === 'INTEGRATION' && accessToken` 을 그대로
      // 넣어 standalone 에서 `Authorization: false` 가 매 요청에 실렸다.
      ...(MODE === 'INTEGRATION' && accessToken
        ? { Authorization: accessToken }
        : {}),
    };

    // 인자 없이 클로저만 읽는다 — 예전 시그니처(userName, token, loginedSession,
    // accessToken)는 visibilitychange 에서 userName 을 빼고 호출해 헤더가 한 칸씩
    // 밀려 있었다(jf-User 에 token 이 들어갔다).
    const connectSSE = () => {
      const source = new EventSourcePolyfill(url, { headers });
      eventSourceRef.current = source;

      source.onopen = () => {
        retry.attempt = 0;
      };

      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // ✅ 상태 업데이트
          setAlarmCount(Number(data?.not_read_count) || 0);
          retry.attempt = 0;
        } catch (error) {
          console.error('SSE 메시지 파싱 오류:', error);
        }
      };

      // async 함수를 onerror 에 직접 대입하면 내부 예외가 미처리 rejection 으로 샌다.
      // 동기 래퍼가 fire-and-forget 으로 부르고, 몸통은 try/catch 로 감싼다
      // (useDashboardSse.jsx 와 같은 형태).
      const handleErrorReset = async (error) => {
        try {
          source.close();

          // 만료면 classifySseFailure 가 자동 로그아웃까지 처리한다(network.js 에서 한 번 더
          // 확인한 뒤 실제 로그아웃). 권한없음/영구실패면 재연결이 무의미하다.
          const verdict = await classifySseFailure({
            errorEvent: error,
            url,
            headers,
          });
          // FATAL(권한없음)만 영구 중단이다. EXPIRED 는 **잠정** 판정이다 —
          // network.js 가 한 번 더 확인해 "세션 유지"로 뒤집을 수 있는데, 여기서 영구
          // 중단하면 세션이 멀쩡한데 알람 스트림만 죽는다. 그래서 EXPIRED 는 아래
          // 백오프(GIVE_UP_AFTER 상한)에 맡긴다 — 진짜 만료면 곧 /login 으로 나가며
          // 이 컴포넌트가 언마운트되고, 오탐이면 재연결로 스스로 복구된다.
          if (verdict === SSE_FAILURE.FATAL) {
            stopped = true;
            return;
          }

          // probe 를 await 하는 동안 언마운트/의존성 변경됐으면 아무도 정리하지 못하는
          // 타이머가 남는다.
          if (!isCurrent) return;
          // 탭이 숨은 사이 늦게 resolve 된 핸들러가 재연결을 예약하면, 그 타이머는 이미
          // 끝난 disconnectSSE 가 잡을 수 없다. 복귀 시 visibility 핸들러가 연결한다.
          if (document.visibilityState !== 'visible') return;
          if (retry.attempt >= SSE_RETRY.GIVE_UP_AFTER) return;
          const delay = sseRetryDelay(retry.attempt);
          retry.attempt += 1;
          retryTimeout = setTimeout(() => {
            if (isCurrent && !stopped) connectSSE();
          }, delay);
        } catch (e) {
          console.error('SSE 오류 처리 실패:', e);
        }
      };

      source.onerror = (error) => {
        handleErrorReset(error);
      };
    };

    const disconnectSSE = () => {
      clearTimeout(retryTimeout);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // 만료/권한없음으로 확정 중단된 상태면 되살리지 않는다 — 같은 실패와
        // handleSessionExpired 재호출을 반복하게 된다.
        if (stopped) return;
        // 탭 복귀 시엔 백오프를 초기화하고 새로 연결한다(중복 연결 방지로 먼저 정리).
        disconnectSSE();
        retry.attempt = 0;
        connectSSE();
      } else {
        disconnectSSE();
      }
    };

    connectSSE();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // ** useEffect cleanup function **
    // 예전엔 eventSourceRef.current 가 있을 때만 정리해서, 연결 실패 상태로 언마운트되면
    // visibilitychange 리스너가 그대로 남았다.
    return () => {
      isCurrent = false;
      disconnectSSE();
      isLoading.current = false;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [userName]);

  const isLoading = useRef(false);

  return (
    <div className={cx('alarm-outer-cont')}>
      <div className={cx('alarm-cont')} onClick={() => handleAlarmToggle()}>
        <div className={cx('center-cont')}>
          <img src={AlarmIcon} className={cx('alarm-icon')} alt='alarm-icon' />
          {alarmCount !== 0 && (
            <div className={cx('circle', 'red')}>
              <span>{alarmCount > 99 ? '99+' : alarmCount}</span>
            </div>
          )}
        </div>
      </div>
      {isOpen && (
        <AlarmDetail
          isLoading={isLoading}
          alarmList={alarmList}
          handleAlarmToggle={handleAlarmToggle}
          getAlarmList={getAlarmList}
        />
      )}
    </div>
  );
};

export default Alarm;
