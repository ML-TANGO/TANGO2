import { ButtonV2, Loading } from '@jonathan/ui-react';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

// Actions
import { closeModal } from '@src/store/modules/modal';
import useIntervalCall from '@src/hooks/useIntervalCall';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './FineTuningSystemLogModal.module.scss';

const cx = classNames.bind(style);

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
  const [footerMessage, setFooterMessage] = useState('');
  const [isPending, setIsPending] = useState(false);

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
    setIsPending(true);
    if (isFirstFetch.current) {
      setLoading(true);
    }
    const url = isExternal
      ? `external/jobs/${targetId}/system-log`
      : `models/fine-tuning/system-log?model_id=${targetId}`;
    const response = await callApi({
      url,
      method: 'get',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      setLog(result);
    } else {
      errorToastMessage(error, message);
    }
    if (isFirstFetch.current) {
      setLoading(false);
      isFirstFetch.current = false;
    }
    isPendingRef.current = false;
  }, [targetId, isExternal]);

  useEffect(() => {
    getSystemLog();

    const intervalId = setInterval(() => {
      if (!isPendingRef.current) {
        getSystemLog();
      }
    }, 1000);

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
            disabled={
              isExternal || loading || !log || log.length === 0
            }
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
