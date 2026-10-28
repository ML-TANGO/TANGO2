import { useCallback, useEffect, useRef } from 'react';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import {
  classifySseFailure,
  createSseRetryState,
  SSE_FAILURE,
  SSE_RETRY,
  sseRetryDelay,
} from '@src/utils/sse';

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
  // 6개 SSE 소비처 공용 재시도 상태(정책·백오프·상한은 utils/sse 한 곳에서 공유).
  // 이 화면은 SSE 3개(status/graph/time)를 동시에 열어 토스트는 붙이지 않는다 —
  // 실패 1건에 안내가 3개 뜬다. 알림만 표면별 opt-in 이고 메커니즘은 6곳 동일하다.
  const retryRef = useRef(createSseRetryState());

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
        // 연결 성공 = 연속 실패 사슬 종료. 리셋하지 않으면 백오프가 최대치로 고착되고
        // 상한에 걸려 재연결이 영구 중단된다.
        retryRef.current.attempt = 0;
        retryRef.current.notified = false;
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

      eventSourceRef.current.onerror = async (error) => {
        console.error('SSE error:', error);
        eventSourceRef.current.close();

        // 만료(→자동 로그아웃)/권한 없음(→영구 실패)에는 재연결하지 않는다.
        const verdict = await classifySseFailure({
          errorEvent: error,
          url,
          headers: option.headers,
        });
        // await 동안(probe 최대 5s) 언마운트됐으면 멈춘다 — 아니면 cleanup 이 추적하지
        // 못하는 타이머/EventSource 를 새로 만들어 좀비 재연결 루프가 남는다.
        if (!retryRef.current.alive) return;
        if (verdict !== SSE_FAILURE.RETRY) return;
        if (retryRef.current.attempt >= SSE_RETRY.GIVE_UP_AFTER) return;

        if (fineTuningStatus === 'running') {
          const delay = sseRetryDelay(retryRef.current.attempt);
          retryRef.current.attempt += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            if (retryRef.current.alive) connectSSE();
          }, delay);
        }
      };
    };

    // 재마운트 시 cleanup 이 내린 alive 를 다시 올린다(ref 는 마운트 간 유지되므로 필수).
    retryRef.current.alive = true;
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
      // 진행 중인 classifySseFailure await 가 늦게 resolve 돼도 재연결하지 않도록 먼저 내린다.
      retryRef.current.alive = false;
      if (eventSourceRef.current) {
        console.log('sse 페이지 나감 cleanup');
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [
    modelId,
    userName,
    setProgressData,
    fineTuningStatus,
    mode,
    disconnectSSE,
  ]);
};

export default useSSEFinetuningTime;
