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
//   'internal' (default) → /api/models/fine-tuning/sse-time/{modelId}
//   'external'           → /api/external/jobs/{jobId}/sse-time
const useSSEFinetuningTime = (
  modelId,
  userName,
  setProgressData,
  fineTuningStatus,
  mode = 'internal',
) => {
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // finetuning progress
  //

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
    // if (!modelId || fineTuningStatus !== 'running') {
    if (!modelId || !fineTuningStatus || fineTuningStatus !== 'running') {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const connectSSE = () => {
      const url =
        mode === 'external'
          ? `${API_HOST}external/jobs/${modelId}/sse-time`
          : `${API_HOST}models/fine-tuning/sse-time/${modelId}`;
      const option = {
        headers: {
          // 'Content-Type': 'application/json;charset=UTF-8',
          'Content-Type': 'text/event-stream',
          'jf-User': userName || 'login',
          'jf-Token': token || 'login',
          'jf-Session': loginedSession || 'login',
          Authorization: MODE === 'INTEGRATION' ? accessToken : undefined,
        },
      };

      eventSourceRef.current = new EventSourcePolyfill(url, option);

      eventSourceRef.current.onopen = (d) => {
        console.log('SSE connection opened', d);
      };

      eventSourceRef.current.onmessage = (event) => {
        try {
          if (!event.data || !event.data.trim()) return;
          const data = JSON.parse(event.data);

          setProgressData(data);
        } catch (error) {
          console.error('Error SSE:', error);
        }
      };

      eventSourceRef.current.onerror = (error) => {
        console.error('SSE error:', error);
        eventSourceRef.current.close();

        if (fineTuningStatus === 'running') {
          reconnectTimeoutRef.current = setTimeout(connectSSE, 5000);
        }
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
  }, [modelId, userName, setProgressData, fineTuningStatus, mode, disconnectSSE]);
};

export default useSSEFinetuningTime;
