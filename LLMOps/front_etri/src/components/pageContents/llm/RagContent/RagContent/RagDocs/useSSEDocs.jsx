import { useCallback, useEffect, useRef } from 'react';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

const useSSEDocs = (ragId, userName, setData) => {
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

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
    if (!ragId) return;

    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const connectSSE = () => {
      const url = `${API_HOST}rags/documents/${ragId}`;
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
          const data = JSON.parse(event.data);
          console.log('docs 연결', data);
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
      if (eventSourceRef.current) {
        console.log('sse 페이지 나감 cleanup');
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [ragId, userName, setData, disconnectSSE]);
};

export default useSSEDocs;
