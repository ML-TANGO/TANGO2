import { useCallback, useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

const usePreprocessSse = ({ did }) => {
  const [data, setData] = useState({ status: '' });
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const { auth } = useSelector((state) => ({
    auth: state.auth,
    headerOptions: state.headerOptions,
  }));

  const { userName } = auth;

  const connectSSE = useCallback(() => {
    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const url = `${API_HOST}preprocessing/sse/status?preprocessing_id=${did}`;
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
  }, [did, userName]);

  const disconnectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('Disconnecting SSE');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    connectSSE();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Tab is active, reconnecting SSE');
        connectSSE();
      } else {
        console.log('Tab is inactive, disconnecting SSE');
        disconnectSSE();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      disconnectSSE();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [connectSSE, disconnectSSE]);

  return { data };
};

export default usePreprocessSse;
