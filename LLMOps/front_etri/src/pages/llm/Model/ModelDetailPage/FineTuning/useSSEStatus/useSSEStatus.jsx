import { useCallback, useEffect, useRef } from 'react';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

const API_HOST_ENV = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = API_HOST_ENV
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;
const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

// `mode`:
//   'internal' (default) → /api/models/fine-tuning/sse-status/{modelId}
//   'external'           → /api/external/jobs/{jobId}/sse-status
// External jobs reuse the same payload shape (see apps/llm_model/src/external/route.py).
const useSSEStatus = (modelId, userName, setData, mode = 'internal') => {
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
    if (!modelId) return;

    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const connectSSE = () => {
      const url =
        mode === 'external'
          ? `${API_HOST}external/jobs/${modelId}/sse-status`
          : `${API_HOST}models/fine-tuning/sse-status/${modelId}`;
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
        // console.log('SSE connection opened');
      };

      eventSourceRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // data {fine_tuning_status:  {status: 'done', reason: ''}, commit_status:{status: 'done', reason: ''} }

          // fine_tuning_status > status > stop, done 빼고 모두 비활성화\
          setData(data);
        } catch (error) {
          console.error('Error SSE:', error);
        }
      };

      eventSourceRef.current.onerror = (error) => {
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
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [modelId, userName, setData, mode, disconnectSSE]);
};

export default useSSEStatus;
