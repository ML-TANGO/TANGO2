import { useEffect, useRef } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import { handleRagReset, handleSetRagState } from '@src/store/modules/llmRag';
import { STATUS_SUCCESS } from '@src/network';

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

const useSSESettingStatus = (ragId, userName, setData) => {
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    if (!ragId) return;

    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const connectSSE = () => {
      console.log('재연결');
      const url = `${API_HOST}rags/setting/${ragId}`;
      const option = {
        headers: {
          'Content-Type': 'application/json;charset=UTF-8',
          'jf-User': userName || 'login',
          'jf-Token': token || 'login',
          'jf-Session': loginedSession || 'login',
          Authorization: MODE === 'INTEGRATION' ? accessToken : undefined,
        },
      };
      eventSourceRef.current = new EventSourcePolyfill(url, option);

      eventSourceRef.current.onopen = () => {
        console.log('SSE connection opened');
      };

      eventSourceRef.current.onmessage = (event) => {
        try {
          if (!event.data || !event.data.trim()) {
            console.warn('Received empty data from SSE');
            return;
          }
          const data = JSON.parse(event.data);

          setData(data);
        } catch (error) {
          console.error('Error SSE:', error);
        }
      };

      eventSourceRef.current.onerror = (error) => {
        console.error('SSE error:', error);
        eventSourceRef.current.close();
        reconnectTimeoutRef.current = setTimeout(connectSSE, 5000);
      };
    };

    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        console.log('sse 페이지 나감 cleanup');
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [ragId, userName, setData]);
};

export default useSSESettingStatus;
