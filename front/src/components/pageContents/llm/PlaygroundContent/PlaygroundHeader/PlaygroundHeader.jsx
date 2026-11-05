import { useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { EventSourcePolyfill } from 'event-source-polyfill';

import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';
import {
  classifySseFailure,
  SSE_FAILURE,
  SSE_RETRY,
  sseRetryDelay,
} from '@src/utils/sse';

import Message from './Message';
import OutsideWarn from './OutsideWarn/OutsideWarn';
import PlaygroundButtonCont from './PlaygroundButtonCont';
import PlaygroundNavigation from './PlaygroundNavigation/PlaygroundNavigation';

import classNames from 'classnames/bind';
import style from './PlaygroundHeader.module.scss';

const APP_LOCAL_HOST = import.meta.env.VITE_REACT_APP_API_HOST === 'local';
const API_HOST = APP_LOCAL_HOST
  ? '/api/'
  : `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

const cx = classNames.bind(style);

// ** [계산] 배포 버튼 로딩 **
export const calIsDeployLoading = (statusType) => {
  if (statusType === 'installing') return true;
  if (statusType === 'pending') return true;
  return false;
};

const PlaygroundHeader = ({
  title,
  getDetailPlaygroundInfo,
  eventSourceRef,
  skipFirstDetailRefresh = false,
}) => {
  const history = useHistory();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { did: playgroundId } = match.params;

  // ** [데이터] 초기 SSE Fetch Loading **
  const [isFetchingStatus, setIsFetchingStatus] = useState(true);

  // SSE 재시도 상태 — effect 지역변수로 두면 재마운트마다 초기화돼 토스트가 되살아난다.
  const retryCountRef = useRef(0);
  const errorNotifiedRef = useRef(false);
  // classifySseFailure 는 probe fetch 를 기다려 최대 5초 await 된다. 그 사이 언마운트되면
  // cleanup 이 이미 끝나 있어, 늦게 resolve 된 핸들러가 만드는 타이머/EventSource 는
  // 아무도 정리하지 못한다(좀비 재연결 루프). 그래서 재연결 직전에 이 값을 검사한다.
  const aliveRef = useRef(true);
  const sseUrlRef = useRef(null);
  const firstMessageRef = useRef(true);

  // ! [사이드 이펙트] SSE 연동
  useEffect(() => {
    let errorTimeout;

    // ** SSE **
    const connectSSE = (playgroundId) => {
      // 안내 토스트는 첫 실패 1회만, 재시도는 조용한 지수 백오프.
      // 세션 만료 → 자동 로그아웃(유틸), 권한 없음/영구 실패 → 재시도 중단.
      // 연속 실패가 이어지면 기존 동작대로 상태를 비우고 이전 화면으로 빠져나간다.
      // 상한은 6곳 공용 상수를 쓴다(예전엔 여기만 로컬 6, 대시보드는 무제한이었다).
      const GIVE_UP_AFTER = SSE_RETRY.GIVE_UP_AFTER;
      const bailOut = () => {
        dispatch(handleSetPlaygroundState({ type: 'status', status: '' }));
        clearTimeout(errorTimeout);
        eventSourceRef.current?.close();
      };

      const handleErrorReset = async (error) => {
        eventSourceRef.current?.close();
        console.log('[SSE CONNECT ERROR] ', error);

        const verdict = await classifySseFailure({
          errorEvent: error,
          url: sseUrlRef.current,
        });
        if (verdict === SSE_FAILURE.EXPIRED) return;
        if (verdict === SSE_FAILURE.FATAL) {
          if (!errorNotifiedRef.current) {
            errorNotifiedRef.current = true;
            toast.error(
              '[SSE] 이 배포 상태에 접근할 수 없어 실시간 갱신을 중단합니다.',
            );
          }
          bailOut();
          return;
        }

        if (!errorNotifiedRef.current) {
          errorNotifiedRef.current = true;
          toast.error(
            '[SSE CONNECT ERROR] SSE 연결이 끊어졌습니다. 재연결을 시도합니다.',
          );
        }

        // await 후 언마운트 확인 — 화면을 이미 벗어났다면 bailOut(history.goBack)도
        // 재연결도 하지 않는다(정리 불가한 타이머/EventSource 를 만들지 않기 위함).
        if (!aliveRef.current) return;

        if (retryCountRef.current >= GIVE_UP_AFTER) {
          bailOut();
          history.goBack(-1);
          return;
        }

        const delay = sseRetryDelay(retryCountRef.current);
        retryCountRef.current += 1;
        errorTimeout = setTimeout(() => {
          if (aliveRef.current) connectSSE(playgroundId);
        }, delay);
      };

      const url = `${API_HOST}playgrounds/status/${playgroundId}`;
      sseUrlRef.current = url;
      eventSourceRef.current = new EventSourcePolyfill(url);
      eventSourceRef.current.onopen = () => {
        retryCountRef.current = 0;
        errorNotifiedRef.current = false;
      };
      setIsFetchingStatus(true);

      eventSourceRef.current.onmessage = (event) => {
        try {
          if (!event.data) {
            console.log('SSE ping');
            return;
          }
          const data = JSON.parse(event.data);
          dispatch(
            handleSetPlaygroundState({
              type: 'status',
              status: data,
            }),
          );
          // 정규화에 쓴 최초 GET으로 Redux도 수화했으므로 첫 SSE에서 같은 상세 GET을 중복하지 않는다.
          if (!skipFirstDetailRefresh || !firstMessageRef.current) {
            getDetailPlaygroundInfo(dispatch, +playgroundId);
          }
          firstMessageRef.current = false;
          setIsFetchingStatus(false);
          if (errorTimeout) {
            retryCountRef.current = 0;
            errorNotifiedRef.current = false;
            clearTimeout(errorTimeout);
          }
        } catch (error) {
          handleErrorReset(error);
        }
      };

      eventSourceRef.current.onerror = (error) => {
        handleErrorReset(error);
      };
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Tab is active, reconnecting SSE');
        connectSSE(playgroundId);
      } else {
        console.log('Tab is inactive, disconnecting SSE');
        eventSourceRef.current.close();
        clearTimeout(errorTimeout);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    // 재마운트 시 cleanup 이 내린 alive 를 다시 올린다(ref 는 마운트 간 유지되므로 필수).
    aliveRef.current = true;
    connectSSE(playgroundId);

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

  return (
    <div className={cx('header-cont')}>
      <OutsideWarn />
      <PlaygroundNavigation />
      <div className={cx('header-content-cont')}>
        <h2 className={cx('header-title')}>{title}</h2>
        <div className={cx('header-content-right')}>
          <Message isFetchingStatus={isFetchingStatus} />
          <PlaygroundButtonCont isFetchingStatus={isFetchingStatus} />
        </div>
      </div>
    </div>
  );
};

export default PlaygroundHeader;
