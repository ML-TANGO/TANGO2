import { useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { EventSourcePolyfill } from 'event-source-polyfill';

import {
  DEFAULT_DATA_STORAGE,
  DEFAULT_HISTORY,
  DEFAULT_INFO,
  DEFAULT_INSTANCE_USED,
  DEFAULT_ISMANAGER,
  DEFAULT_MAIN_STORAGE,
  DEFAULT_TOTAL_COUNT,
  DEFAULT_USAGE,
} from '../constant';

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

const useDashboardSSe = (workspaceId) => {
  const { auth } = useSelector((state) => ({
    auth: state.auth,
    headerOptions: state.headerOptions,
  }));
  const { userName } = auth;
  const eventSourceRef = useRef(null);

  const [info, setInfo] = useState(DEFAULT_INFO);
  const [history, setHistory] = useState(DEFAULT_HISTORY);
  const [totalCount, setTotalCount] = useState(DEFAULT_TOTAL_COUNT);
  const [usage, setUsage] = useState(DEFAULT_USAGE);
  const [mainStorage, setMainStorage] = useState(DEFAULT_MAIN_STORAGE);
  const [dataStorage, setDataStorage] = useState(DEFAULT_DATA_STORAGE);
  const [instanceUsed, setInstanceUsed] = useState(DEFAULT_INSTANCE_USED);
  const [isManager, setIsManager] = useState(DEFAULT_ISMANAGER);

  useEffect(() => {
    let recount = 0;
    let errorTimeout;

    // ** SSE **
    const connectSSE = () => {
      const handleErrorReset = (error) => {
        eventSourceRef.current.close();
        toast.error('[SSE CONNECT ERROR] SSE 연결이 끊어졌습니다.');
        console.log('[SSE CONNECT ERROR] ', error);

        errorTimeout = setTimeout(() => {
          if (recount < 6) {
            recount++;
            toast.error(
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

      const keyToStateMap = {
        info: setInfo,
        history: setHistory,
        total_count: setTotalCount,
        usage: setUsage,
        storage: (storageData) => {
          setMainStorage(storageData.main_storage);
          setDataStorage(storageData.data_storage);
        },
        manager: setIsManager,
        instances_used: setInstanceUsed,
      };

      eventSourceRef.current.onmessage = (event) => {
        try {
          if (!event.data) {
            console.log('SSE ping');
            return;
          }

          const data = JSON.parse(event.data);
          const key = Object.keys(data)[0];
          const setterFunction = keyToStateMap[key];

          if (setterFunction) {
            if (key === 'storage') {
              setterFunction(data.storage);
            } else {
              setterFunction(data[key]);
            }
          }

          if (errorTimeout) {
            recount = 0;
            clearTimeout(errorTimeout);
          }
        } catch (error) {
          console.log(error);
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
  }, []);

  return [
    info,
    history,
    totalCount,
    usage,
    mainStorage,
    dataStorage,
    isManager,
    instanceUsed,
  ];
};

export default useDashboardSSe;
