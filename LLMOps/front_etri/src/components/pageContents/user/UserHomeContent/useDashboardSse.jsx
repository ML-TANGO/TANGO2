import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { EventSourcePolyfill } from 'event-source-polyfill';

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
  const { auth } = useSelector((state) => ({
    auth: state.auth,
    headerOptions: state.headerOptions,
  }));
  const { userName } = auth;

  useEffect(() => {
    let recount = 0;
    let errorTimeout;

    // ** SSE **
    const connectSSE = () => {
      const handleErrorReset = (error) => {
        eventSourceRef.current.close();
        console.warn('[SSE CONNECT ERROR] SSE 연결이 끊어졌습니다.');
        console.log('[SSE CONNECT ERROR] ', error);

        errorTimeout = setTimeout(() => {
          if (recount < 6) {
            recount++;
            console.warn(
              `[${recount}번 연결 시도] SSE 연결을 다시 시도합니다. 최대 5번까지 시도합니다. 5번 실패 후 메뉴 페이지로 나가게 됩니다. `,
            );
            connectSSE();
          } else {
            clearTimeout(errorTimeout);
            eventSourceRef.current.close();
            // history.goBack(-1);
          }
        }, 1000);
      };
      const option = {
        headers: {
          'Content-Type': 'application/json;charset=UTF-8',
          'jf-User': userName || 'login',
        },
      };

      const url = `${API_HOST}dashboard/user/sse?workspace_id=${workspaceId}&platform_type=a-llm`;
      eventSourceRef.current = new EventSourcePolyfill(url, option);

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
            recount = 0;
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
    connectSSE();

    // ** useEffect cleanup function **
    return () => {
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
