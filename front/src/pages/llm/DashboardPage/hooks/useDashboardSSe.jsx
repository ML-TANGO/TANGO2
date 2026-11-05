import { useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { EventSourcePolyfill } from 'event-source-polyfill';

import {
  classifySseFailure,
  SSE_FAILURE,
  SSE_RETRY,
  sseRetryDelay,
} from '@src/utils/sse';

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
  // 재마운트/의존성 변경에도 유지돼야 하는 재시도 상태(기존엔 useEffect 지역변수라
  // 화면을 옮기면 0으로 초기화 → 토스트 폭주가 매번 되살아났다).
  const retryCountRef = useRef(0);
  const errorNotifiedRef = useRef(false);
  // classifySseFailure 는 probe fetch 를 기다려 최대 5초 await 된다. 그 사이 언마운트되면
  // cleanup 이 이미 끝나 있어, 늦게 resolve 된 핸들러가 만드는 타이머/EventSource 는
  // 아무도 정리하지 못한다(좀비 재연결 루프). 그래서 재연결 직전에 이 값을 검사한다.
  const aliveRef = useRef(true);
  const sseUrlRef = useRef(null);
  const sseHeadersRef = useRef(null);

  const [info, setInfo] = useState(DEFAULT_INFO);
  const [history, setHistory] = useState(DEFAULT_HISTORY);
  const [totalCount, setTotalCount] = useState(DEFAULT_TOTAL_COUNT);
  const [usage, setUsage] = useState(DEFAULT_USAGE);
  const [mainStorage, setMainStorage] = useState(DEFAULT_MAIN_STORAGE);
  const [dataStorage, setDataStorage] = useState(DEFAULT_DATA_STORAGE);
  const [instanceUsed, setInstanceUsed] = useState(DEFAULT_INSTANCE_USED);
  const [isManager, setIsManager] = useState(DEFAULT_ISMANAGER);

  useEffect(() => {
    let errorTimeout;

    // ** SSE **
    const connectSSE = () => {
      // 재연결 실패를 매번 토스트로 알리면(기존: 실패 1건당 1+최대6개) 화면이 토스트로
      // 덮인다. 안내는 첫 실패 1회만, 이후는 조용히 지수 백오프로 재시도한다.
      // 세션 만료(→자동 로그아웃)/권한 없음(→영구 실패)은 classifySseFailure 가 구분한다.
      const handleErrorReset = async (error) => {
        eventSourceRef.current?.close();
        console.log('[SSE CONNECT ERROR] ', error);

        const verdict = await classifySseFailure({
          errorEvent: error,
          url: sseUrlRef.current,
          headers: sseHeadersRef.current,
        });
        // 만료: 유틸이 이미 자동 로그아웃 처리 → 재연결/토스트 없이 종료.
        // 영구 실패(권한 없음 등): 재시도해도 같은 결과 → 1회만 알리고 종료.
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
        // 지수 백오프 1s → 2s → 4s … 최대 30s(6곳 공용 sseRetryDelay).
        // 상한(SSE_RETRY.GIVE_UP_AFTER)을 둔다 — 예전엔 상한이 없어 영구히 죽은 서버에도
        // 30초마다 계속 요청했고, PlaygroundHeader 는 6회 제한이라 정책이 갈려 있었다.
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
      // 실패 원인 판별(만료 vs 권한 vs 일시 장애)은 같은 URL/헤더 재조회가 필요하다.
      sseUrlRef.current = url;
      sseHeadersRef.current = option.headers;
      eventSourceRef.current = new EventSourcePolyfill(url, option);
      eventSourceRef.current.onopen = () => {
        // 연결 성공 → 백오프/토스트 상태 초기화(다음 장애 때 다시 1회 안내).
        retryCountRef.current = 0;
        errorNotifiedRef.current = false;
      };

      const keyToStateMap = {
        info: setInfo,
        history: setHistory,
        total_count: setTotalCount,
        usage: setUsage,
        storage: (storageData) => {
          setMainStorage(storageData?.main_storage ?? DEFAULT_MAIN_STORAGE);
          setDataStorage(storageData?.data_storage ?? DEFAULT_DATA_STORAGE);
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
            retryCountRef.current = 0;
            errorNotifiedRef.current = false;
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
