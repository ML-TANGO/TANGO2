import { ButtonV2, Loading } from '@jonathan/ui-react';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

// Actions
import { closeModal } from '@src/store/modules/modal';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './FineTuningSystemLogModal.module.scss';

const cx = classNames.bind(style);
const SYSTEM_LOG_REQUEST_TIMEOUT_MS = 12000;

const FineTuningSystemLogModal = ({ data, type }) => {
  // External-mode callers pass `{ jobId, manifestName, mode: 'external' }`;
  // internal callers pass `{ modelId, modelName }` and `mode` defaults to 'internal'.
  // For external v1.0.0 the BFF returns a platform-side placeholder string —
  // raw partner log streaming lands when ETRI v1.0.1 exposes /train/log.
  const { modelId, modelName, jobId, manifestName, mode = 'internal' } = data;
  const isExternal = mode === 'external';
  const targetId = isExternal ? jobId : modelId;
  const displayName = isExternal ? manifestName : modelName;
  const dispatch = useDispatch();
  const isFirstFetch = useRef(true);
  const isPendingRef = useRef(false);
  const [log, setLog] = useState('');
  const [loading, setLoading] = useState(true);
  const footerMessage = '';

  const { t } = useTranslation();

  const onClickDownload = async () => {
    if (isExternal) {
      // v1.0.0 BFF doesn't expose a download endpoint; the button is disabled,
      // so this branch is defensive only.
      return;
    }
    const { data, status } = await network.callApiWithPromise({
      url: `models/fine-tuning/system-log/download?model_id=${modelId}`,
      method: 'GET',
    });

    if (status === 200) {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[Finetuning]No.${modelId}.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      errorToastMessage();
    }
  };

  // GET 학습
  const getSystemLog = useCallback(async () => {
    if (isPendingRef.current) return;
    isPendingRef.current = true;
    if (isFirstFetch.current) {
      setLoading(true);
    }
    if (!targetId) {
      setLog('');
      if (isFirstFetch.current) {
        setLoading(false);
        isFirstFetch.current = false;
      }
      isPendingRef.current = false;
      return;
    }
    const url = isExternal
      ? `external/jobs/${targetId}/system-log`
      : `models/fine-tuning/system-log?model_id=${targetId}`;
    const controller = new AbortController();
    let didTimeout = false;
    const timeoutId = setTimeout(() => {
      didTimeout = true;
      controller.abort();
    }, SYSTEM_LOG_REQUEST_TIMEOUT_MS);

    try {
      const response = await callApi({
        url,
        method: 'get',
        signal: controller.signal,
      });

      const { status, result, message, error } = response;

      if (status === STATUS_SUCCESS) {
        // 동시 폴링 부하로 간헐적으로 placeholder(train.log 미발견)가 올 수 있다.
        // 실제 로그(BFF 헤더에 'showing last')이거나 아직 표시할 로그가 없을 때만
        // 갱신 — placeholder/빈값으로 이미 표시 중인 실제 로그를 덮어쓰지 않는다
        // (flicker 방지).
        setLog((prev) => {
          if (!result) return prev;
          if (!isExternal) return result;
          const prevIsTimeout =
            typeof prev === 'string' &&
            prev.startsWith('[platform] system-log request timed out');
          if (
            result.includes('showing last') ||
            !prev ||
            prev.length === 0 ||
            prevIsTimeout
          ) {
            return result;
          }
          return prev;
        });
      } else if (didTimeout) {
        setLog((prev) =>
          prev && prev.length > 0
            ? prev
            : `[platform] system-log request timed out after ${
                SYSTEM_LOG_REQUEST_TIMEOUT_MS / 1000
              }s.\nThe backend is still reachable only after the log endpoint responds.`,
        );
      } else {
        errorToastMessage(error, message);
      }
    } finally {
      clearTimeout(timeoutId);
      if (isFirstFetch.current) {
        setLoading(false);
        isFirstFetch.current = false;
      }
      isPendingRef.current = false;
    }
  }, [targetId, isExternal]);

  useEffect(() => {
    getSystemLog();

    const intervalId = setInterval(() => {
      if (!isPendingRef.current) {
        getSystemLog();
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [getSystemLog]);

  return (
    <NewStyleModalFrame
      title={t('systemLog.label')}
      type={type}
      submit={{
        text: t('confirm.label'),
        func: () => {
          dispatch(closeModal('FINETUNING_SYSTEM_LOG'));
        },
      }}
      validate={true}
      isResize={true}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('container')}>
        <div className={cx('title')}>
          <div className={cx('name')}>{displayName ?? '-'}</div>
          <ButtonV2
            type='solid'
            size='l'
            colorType='skyblue'
            label={t('logDownload.label')}
            disabled={isExternal || loading || !log || log.length === 0}
            onClick={onClickDownload}
          />
        </div>
        {loading && (
          <div className={cx('noData')}>
            <Loading />
          </div>
        )}

        {!loading && (!log || log.length === 0) && (
          <div className={cx('noData')}> {t('noData.message')}</div>
        )}

        {!loading && log && log.length > 0 && (
          <div className={cx('content')}>{log}</div>
        )}
      </div>
    </NewStyleModalFrame>
  );
};

export default FineTuningSystemLogModal;
