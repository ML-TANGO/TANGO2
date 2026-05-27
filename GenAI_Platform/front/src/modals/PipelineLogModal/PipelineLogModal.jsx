import React, { useEffect, useState } from 'react';
import { toast } from 'react-toastify';

import { Badge, ButtonV2 } from '@jonathan/ui-react';

import dayjs from 'dayjs';

import Spinner from '@src/components/atoms/Spinner';
import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';

import {
  getPipelineLog,
  getPipelineSystemLogdownload,
} from '@src/apis/flightbase/pipeline';
import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './PipelineLogModal.module.scss';

const cx = classNames.bind(style);

const calTaskTypeLabel = (taskType) => {
  if (taskType === 'pre')
    return { color: 'primary-2', label: '학습 데이터 전처리' };
  if (taskType === 'train') return { color: 'orange', label: '학습' };
  return { color: 'green', label: '배포' };
};

const getPipelineLogContents = async (taskId, setLog) => {
  const { status, message, result } = await getPipelineLog(taskId);
  if (status === STATUS_SUCCESS) {
    setLog(result);
  } else {
    toast.error(message);
  }
};

const handleLogdownload = async (taskId) => {
  const { data, status, message } = await getPipelineSystemLogdownload(taskId);

  if (status === 200) {
    const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `[${taskId}-LOG] ${dayjs().format('YYYYMMDD hhmmss')}.csv`;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } else {
    toast.error(message);
  }
};

export default function PipelineLogModal({ data, type }) {
  const { submit, title, taskName, taskType, taskId } = data;
  const { color, label } = calTaskTypeLabel(taskType);

  const [logLoading, setLogLoading] = useState(true);
  const [log, setLog] = useState('');
  const logMap = log.split('\n');

  useEffect(() => {
    getPipelineLogContents(taskId, setLog);
    setLogLoading(false);

    const interval = setInterval(() => {
      getPipelineLogContents(taskId, setLog);
    }, 1000);

    return () => {
      clearInterval(interval);
    };
  }, [taskId]);

  return (
    <NewStyleModalFrame
      submit={submit}
      type={type}
      validate={true}
      isResize={true}
      isMinimize={true}
      title={title}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('top-cont')}>
        <div className={cx('status-cont')}>
          <Badge label={label} type={color} />
          <h2 className={cx('sub-title')}>{taskName}</h2>
        </div>
        <ButtonV2
          label='로그 다운로드'
          colorType='skyblue'
          onClick={() => handleLogdownload(taskId)}
        />
      </div>
      <div className={cx('paragraph-cont')}>
        {logLoading && (
          <div className={cx('spinner-cont')}>
            <Spinner />
          </div>
        )}
        {!logLoading &&
          logMap.map((el, idx) => (
            <p className={cx('log-paragraph')} key={idx}>
              {el}
            </p>
          ))}
      </div>
    </NewStyleModalFrame>
  );
}
