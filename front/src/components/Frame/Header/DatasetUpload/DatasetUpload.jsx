import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useLocation } from 'react-router-dom';

import { EventSourcePolyfill } from 'event-source-polyfill';
import Cookies from 'universal-cookie';

import UploadDetail from './UploadDetail';

import classNames from 'classnames/bind';
import style from './DatasetUpload.module.scss';

import AlarmIcon from '@src/static/images/icon/ic-upload-alarm.svg';

const cx = classNames.bind(style);

const API_HOST =
  import.meta.env.VITE_REACT_APP_API_HOST ||
  `${window.location.protocol}//${window.location.hostname}:${window.location.port}/api/`;

const MODE = import.meta.env.VITE_REACT_APP_MODE;
const cookies = new Cookies();

const calArrayDifference = (arr1, arr2) => {
  if (!Array.isArray(arr1) || !Array.isArray(arr2)) return {};
  const arrSort1 = arr1.map((obj) => JSON.stringify(obj)).sort();

  const arrSort2 = arr2.map((obj) => JSON.stringify(obj)).sort();

  return arrSort1.reduce((acc, val, idx) => {
    if (val !== arrSort2[idx]) {
      acc[JSON.parse(val).upload_id] = true;
    }
    return acc;
  }, {});
};

const DatasetUpload = () => {
  const dispatch = useDispatch();
  const location = useLocation();
  const pathParts = location.pathname.split('/');

  const currentWorkspaceId = pathParts[3];
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [workspaceId, setWorkspaceId] = useState(currentWorkspaceId);
  const [uploadList, setUploadList] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const isLoading = useRef(false);

  const uploadItemCount = useMemo(() => {
    // uploadList 내부의 모든 items 배열의 요소 개수를 합산
    return uploadList.reduce((acc, current) => {
      return acc + current.items.length;
    }, 0);
  }, [uploadList]);

  const doubleRef = useRef(false);
  const handleUploadToggle = useCallback(() => {
    if (!doubleRef.current) {
      setIsOpen((prev) => !prev);
      doubleRef.current = true;
      setTimeout(() => {
        doubleRef.current = false;
      }, 250);
    }
  }, []);

  const eventSourceRef = useRef(null);

  useEffect(() => {
    if (!workspaceId) return;
    const token = sessionStorage.getItem('token');
    const accessToken = cookies.get('access_token');
    const loginedSession = sessionStorage.getItem('loginedSession');

    const connectSSE = (token, loginedSession, accessToken) => {
      // if (eventSourceRef.current) {
      //   eventSourceRef.current.close(); // 기존 연결 종료
      // }

      const url = `${API_HOST}progress/sse/${workspaceId}`;
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

      // ? eventSource - > SSE를 지원하는 브라우저 API but IE, 구형 브라우저들 지원 x

      eventSourceRef.current.onopen = () => {};

      // eventSourceRef.current.onmessage = (event) => {

      // };

      eventSourceRef.current.onerror = (error) => {
        console.error('SSE error:', error);
        eventSourceRef.current.close();
        if (workspaceId !== undefined) setTimeout(connectSSE, 5000);
      };
    };

    const disconnectSSE = () => {
      if (eventSourceRef.current) {
        console.log('Closing SSE connection');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Tab is active, reconnecting SSE');
        connectSSE(token, loginedSession, accessToken);
      } else {
        console.log('Tab is inactive, disconnecting SSE');
        disconnectSSE();
      }
    };

    connectSSE(token, loginedSession, accessToken);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (eventSourceRef.current) {
        console.log('Closing SSE connection on cleanup');
        eventSourceRef.current.close();
        document.removeEventListener(
          'visibilitychange',
          handleVisibilityChange,
        );
      }
    };
  }, [userName, workspaceId]);

  useEffect(() => {
    //? onmessage 핸들러 한 번 설정해 두기
    //? 이후에 서버가 데이터를 보낼 때마다 onmessage 핸들러가 작동함

    if (eventSourceRef.current) {
      eventSourceRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          let isDiffFound = false;

          setUploadList((prev) => {
            const updatedUploadList = []; // 새로운 배열로 초기화
            let isDiffFound = false;

            if (Object.keys(data).length === 0) {
              return []; // 빈 데이터가 오면 빈 배열 반환
            }

            Object.keys(data).forEach((key) => {
              const datasetName = key; // "o", "a", "b" 등이 datasetName이 됨
              const itemsArray = data[key]; // 각 키에 해당하는 배열을 items로

              // 기존 uploadList에서 datasetName에 해당하는 항목을 찾기
              const prevEntry = prev.find(
                (entry) => entry.datasetName === datasetName,
              );

              // 이전 상태와 새로 들어온 데이터를 비교
              const isDiff = calArrayDifference(
                itemsArray,
                prevEntry ? prevEntry.items : [],
              );

              if (isDiff && Object.keys(isDiff).length) {
                updatedUploadList.push({
                  datasetName: datasetName,
                  items: itemsArray,
                });
                isDiffFound = true; // 변경 사항이 있으면 true로 설정
              } else if (prevEntry) {
                // 변경 사항이 없으면 기존 데이터 유지
                updatedUploadList.push(prevEntry);
              }
            });

            // 변경 사항이 없으면 이전 상태 반환
            return isDiffFound ? updatedUploadList : prev;
          });

          if (!isDiffFound) {
          }
        } catch (error) {
          console.error('Error parsing SSE data:', error);
        }
      };
    }
  }, [uploadList, dispatch, workspaceId]);

  useEffect(() => {
    if (
      currentWorkspaceId !== undefined &&
      workspaceId !== currentWorkspaceId
    ) {
      setWorkspaceId(currentWorkspaceId); // 변경 사항 업데이트
    }
  }, [currentWorkspaceId, workspaceId]);

  return (
    <div className={cx('upload-outer-cont')}>
      <div className={cx('upload-cont')} onClick={() => handleUploadToggle()}>
        <div className={cx('center-cont')}>
          <img
            src={AlarmIcon}
            className={cx('upload-icon')}
            alt='upload-icon'
          />
          {/* {isNotReadAlarm && (
            <div className={cx('circle', 'red')}>
              <span>{alarmCount > 99 ? '99+' : alarmCount}</span>
            </div>
          )} */}
          <div className={cx(uploadItemCount > 0 && 'circle', 'red')}>
            <span>
              {uploadItemCount > 0 &&
                (uploadItemCount > 99 ? '99+' : uploadItemCount)}
            </span>
            {/* <span>99+</span> */}
          </div>
        </div>
        {isOpen && (
          <UploadDetail
            isLoading={isLoading}
            uploadList={uploadList}
            handleUploadToggle={handleUploadToggle}
            workspaceId={workspaceId}
          />
        )}
      </div>
    </div>
  );
};

export default DatasetUpload;
