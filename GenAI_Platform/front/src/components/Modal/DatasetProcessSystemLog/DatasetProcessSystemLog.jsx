import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { callApi, downloadBlob, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './DatasetProcessSystemLog.module.scss';

const cx = classNames.bind(style);

const STATUS_TEXT = {
  pending: '대기',
  done: '종료',
  running: '진행',
  error: '오류',
  installing: '설치중',
};

const DatasetProcessSystemLog = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const [log, setLog] = useState('');

  const { submit, cancel, id, status, name } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      submit.func();
    },
  };

  const fetchLog = async () => {
    const response = await callApi({
      url: `preprocessing/job/system-log?job_id=${id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setLog(result);
    }
  };

  const downloadLog = async () => {
    const result = await downloadBlob({
      url: `preprocessing/job/system-log/download?job_id=${id}`,
    });

    const blobUrl = window.URL.createObjectURL(
      new Blob([result], { type: 'application/octet-stream' }),
    );

    const link = document.createElement('a');
    link.href = blobUrl;
    link.setAttribute('download', `${name}-system-log.txt`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
  };

  useEffect(() => {
    fetchLog();

    const interval = setInterval(() => {
      fetchLog();
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      // cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={t('systemLog.label')}
      customStyle={{ maxHeight: '850px' }}
      validate={true}
    >
      <div className={cx('row')}>
        <div className={cx('header-content')}>
          <div className={cx('left-side')}>
            <div className={cx('status', status)}>{STATUS_TEXT[status]}</div>
            <div className={cx('name')}>{name}</div>
          </div>
          <div className={cx('download-btn')} onClick={downloadLog}>
            로그 다운로드
          </div>
        </div>
        <pre className={cx('log-content')}>{log}</pre>
      </div>
    </NewStyleModalFrame>
  );
};

export default DatasetProcessSystemLog;
