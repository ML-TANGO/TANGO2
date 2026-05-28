// Image
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { shallowEqual, useSelector } from 'react-redux';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import { callApi, STATUS_SUCCESS } from '@src/network';

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
  const eventSourceRef = useRef(null);
  useEffect(() => {
    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const connectSSE = (userName, token, loginedSession, accessToken) => {
      const url = `${API_HOST}notification/sse`;
      const option = {
        headers: {
          'Content-Type': 'application/json;charset=UTF-8',
          'jf-User': userName || 'login',
          'jf-Token': token || 'login',
          'jf-Session': loginedSession || 'login',
          Authorization: MODE === 'INTEGRATION' && accessToken,
        },
      };

      const source = new EventSourcePolyfill(url, option);
      eventSourceRef.current = source;

      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('✅ SSE 수신:', data?.not_read_count);

          // ✅ 상태 업데이트
          setAlarmCount(Number(data?.not_read_count) || 0);
        } catch (error) {
          console.error('SSE 메시지 파싱 오류:', error);
        }
      };

      source.onerror = (error) => {
        console.error('SSE error:', error);

        source.close();

        setTimeout(() => {
          connectSSE(userName, token, loginedSession, accessToken);
        }, 5000);
      };
    };

    const disconnectSSE = () => {
      if (eventSourceRef.current) {
        console.log('Closing SSE connection');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Tab is active, reconnecting SSE');
        connectSSE(token, loginedSession, accessToken);
      } else {
        console.log('Tab is inactive, disconnecting SSE');
        disconnectSSE();
      }
    };

    connectSSE(userName, token, loginedSession, accessToken);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // ** useEffect cleanup function **
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        isLoading.current = false;
        document.removeEventListener(
          'visibilitychange',
          handleVisibilityChange,
        );
      }
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
