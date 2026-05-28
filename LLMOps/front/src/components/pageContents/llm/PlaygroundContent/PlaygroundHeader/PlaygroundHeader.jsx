import { useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { EventSourcePolyfill } from 'event-source-polyfill';

import { handleSetPlaygroundState } from '@src/store/modules/llmPlayground';

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
}) => {
  const history = useHistory();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { did: playgroundId } = match.params;

  // ** [데이터] 초기 SSE Fetch Loading **
  const [isFetchingStatus, setIsFetchingStatus] = useState(true);

  // ! [사이드 이펙트] SSE 연동
  useEffect(() => {
    let recount = 0;
    let errorTimeout;

    // ** SSE **
    const connectSSE = (playgroundId) => {
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
            connectSSE(playgroundId);
          } else {
            dispatch(
              handleSetPlaygroundState({
                type: 'status',
                status: '',
              }),
            );
            clearTimeout(errorTimeout);
            eventSourceRef.current.close();
            history.goBack(-1);
          }
        }, 1000);
      };

      const url = `${API_HOST}playgrounds/status/${playgroundId}`;
      eventSourceRef.current = new EventSourcePolyfill(url);
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
          getDetailPlaygroundInfo(dispatch, +playgroundId);
          setIsFetchingStatus(false);
          if (errorTimeout) {
            recount = 0;
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
    connectSSE(playgroundId);

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

  return (
    <div className={cx('header-cont')}>
      <OutsideWarn />
      <PlaygroundNavigation isFetchingStatus={isFetchingStatus} />
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
