import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { EventSourcePolyfill } from 'event-source-polyfill';

import {
  classifySseFailure,
  SSE_FAILURE,
  SSE_RETRY,
  sseRetryDelay,
} from '@src/utils/sse';

const initial = {
  info: {
    description: '-',
    name: '-',
    status: '',
    period: '0000-00-00 00:00 ~ 0000-00-00 00:00',
    start_datetime: '0000-00-00 00:00',
    end_datetime: '0000-00-00 00:00',
    owner: '-',
    users: [],
  },
  history: null,
  total_count: {
    datasets: '-',
    trainings: '-',
    deployments: '-',
    images: '-',
    models: '-',
    playgrounds: '-',
    prompts: '-',
    rags: '-',
    pricing: '-',
  },
  usage: {
    gpu: {
      total: '-',
      used: '-',
      usage: '-',
    },
    cpu: {
      total: '-',
      used: '-',
      usage: '-',
    },
    ram: {
      total: '-',
      used: '-',
      usage: '-',
    },
    platform_usage: {
      flightbase: {
        cpu: 0,
        ram: 0,
        gpu: 0,
      },
      'a-llm': {
        cpu: 0,
        ram: 0,
        gpu: 0,
      },
    },
  },
  project_items: [],
  storage: {
    main_storage: {
      total: '-',
      used: '-',
      avail: '-',
      usage: '-',
      project_list: null,
      allm_list: null,
    },
    data_storage: {
      total: '-',
      used: '-',
      avail: '-',
      usage: '-',
      dataset_list: null,
    },
  },
  instances_used: null,
  manager: false,
  timeline: [],
  totalCount: [],
  detailed_timeline: [],
};

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

const useDashboardSse = ({ workspaceId }) => {
  const [dashboardData, setDashboardData] = useState(initial);

  const eventSourceRef = useRef(null);
  // 재마운트/의존성 변경에도 유지되는 재시도 상태 + 실패 판별용 URL/헤더.
  const retryCountRef = useRef(0);
  const errorNotifiedRef = useRef(false);
  // classifySseFailure 는 probe fetch 를 기다려 최대 5초 await 된다. 그 사이 언마운트되면
  // cleanup 이 이미 끝나 있어, 늦게 resolve 된 핸들러가 만드는 타이머/EventSource 는
  // 아무도 정리하지 못한다(좀비 재연결 루프). 그래서 재연결 직전에 이 값을 검사한다.
  const aliveRef = useRef(true);
  const sseUrlRef = useRef(null);
  const sseHeadersRef = useRef(null);
  const { auth } = useSelector((state) => ({
    auth: state.auth,
    headerOptions: state.headerOptions,
  }));
  const { userName } = auth;

  useEffect(() => {
    let errorTimeout;

    // ** SSE **
    const connectSSE = () => {
      // 첫 실패 1회만 안내 + 조용한 지수 백오프. 만료는 자동 로그아웃, 권한 없음은 중단.
      // (기존엔 실패 1건당 토스트 1+최대6개, recount 가 지역변수라 재마운트마다 되살아났다.)
      const handleErrorReset = async (error) => {
        eventSourceRef.current?.close();
        console.log('[SSE CONNECT ERROR] ', error);

        const verdict = await classifySseFailure({
          errorEvent: error,
          url: sseUrlRef.current,
          headers: sseHeadersRef.current,
        });
        if (verdict === SSE_FAILURE.EXPIRED) return;
        if (verdict === SSE_FAILURE.FATAL) {
          if (!errorNotifiedRef.current) {
            errorNotifiedRef.current = true;
            toast.error(
              '[SSE] 이 데이터에 접근할 수 없어 실시간 갱신을 중단합니다.',
            );
          }
          return;
        }

        if (!errorNotifiedRef.current) {
          errorNotifiedRef.current = true;
          toast.error(
            '[SSE CONNECT ERROR] SSE 연결이 끊어졌습니다. 재연결을 시도합니다.',
          );
        }

        // await 후 언마운트 확인 — 아니면 cleanup 이 추적 못하는 타이머가 남는다.
        if (!aliveRef.current) return;
        // 상한(6곳 공용 SSE_RETRY.GIVE_UP_AFTER)을 둔다. 예전엔 상한이 없어 영구히 죽은
        // 서버에도 30초마다 계속 요청했다(PlaygroundHeader 는 6회 제한이라 정책이 갈렸다).
        if (retryCountRef.current >= SSE_RETRY.GIVE_UP_AFTER) return;
        const delay = sseRetryDelay(retryCountRef.current);
        retryCountRef.current += 1;
        errorTimeout = setTimeout(() => {
          if (aliveRef.current) connectSSE();
        }, delay);
      };
      const option = {
        headers: {
          'Content-Type': 'application/json;charset=UTF-8',
          'jf-User': userName || 'login',
        },
      };

      const url = `${API_HOST}dashboard/user/sse?workspace_id=${workspaceId}&platform_type=a-llm`;
      sseUrlRef.current = url;
      sseHeadersRef.current = option.headers;
      eventSourceRef.current = new EventSourcePolyfill(url, option);
      eventSourceRef.current.onopen = () => {
        retryCountRef.current = 0;
        errorNotifiedRef.current = false;
      };

      eventSourceRef.current.onmessage = (event) => {
        try {
          if (!event.data) {
            console.log('SSE ping');
            return;
          }

          const data = JSON.parse(event.data);
          const keys = Object.keys(data);

          setDashboardData((prev) => ({
            ...prev,
            [keys[0]]: data[keys],
          }));

          if (errorTimeout) {
            retryCountRef.current = 0;
            errorNotifiedRef.current = false;
            clearTimeout(errorTimeout);
          }
        } catch (error) {
          console.log(error);
          setDashboardData(initial);
          handleErrorReset(error);
        }
      };

      eventSourceRef.current.onerror = (error) => {
        handleErrorReset(error);
        console.log(error);
      };
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Tab is active, reconnecting SSE');
        connectSSE();
      } else {
        console.log('Tab is inactive, disconnecting SSE');
        eventSourceRef.current.close();
        clearTimeout(errorTimeout);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    // 재마운트 시 cleanup 이 내린 alive 를 다시 올린다(ref 는 마운트 간 유지되므로 필수).
    aliveRef.current = true;
    connectSSE();

    // ** useEffect cleanup function **
    return () => {
      // 진행 중인 classifySseFailure await 가 늦게 resolve 돼도 재연결하지 않도록 먼저 내린다.
      aliveRef.current = false;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        clearTimeout(errorTimeout);
      }
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  return { dashboardData };
};

export default useDashboardSse;
