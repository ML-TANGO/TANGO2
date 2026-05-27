import React, { useEffect, useRef, useState } from 'react';
import { useRouteMatch } from 'react-router-dom';

import {
  calConvertMinutes,
  calCurrentTime,
  calFormatSecondToTime,
} from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './PipelineInfoHeader.module.scss';

import IconDotTime from '@src/static/images/icon/00-dot-time.svg';
import IconDataset from '@src/static/images/nav/icon-lnb-storage-blue.svg';

function calculateSecondDifference(time1, time2) {
  const date1 = new Date(time1);
  const date2 = new Date(time2);

  date1.setHours(date1.getHours() + 9);

  const diffInMilliseconds = Math.abs(date2 - date1);
  const diffInSeconds = diffInMilliseconds / 1000;

  return diffInSeconds;
}

const calRetrainTime = (retraining_config) => {
  const { type, unit, value } = retraining_config;
  if (type !== 'time') return `${value} ${unit}`;
  if (unit === 'hours') return `${value} h`;
  const convertValue = calConvertMinutes(value);
  return convertValue;
};

const cx = classNames.bind(style);

const Card = React.memo(({ label, icon, value }) => {
  return (
    <li className={cx('info-item')}>
      <div className={cx('header-cont')}>
        <img src={icon} alt='icon' />
        <span className={cx('label')}>{label}</span>
      </div>
      <span className={cx('value')}>{value.length === 0 ? '-' : value}</span>
    </li>
  );
});

export default function PipelineInfoHeader({
  list,
  retraining_config,
  retraining_wait_start_time,
  isStopBtn,
  handleResetData,
}) {
  const match = useRouteMatch();
  const { params } = match;
  const { tid: pipelineId } = params;

  const { unit, value } = retraining_config;

  const [retrainTimeDataValue, setRetrainTimeDataValue] = useState('');
  const [intervalRetrainTimeValue, setIntervalValue] = useState('-');
  const retrainTimeValue = calRetrainTime(retraining_config);

  useEffect(() => {
    const { type, unit, value } = retraining_config;
    if (type === 'data') {
      setRetrainTimeDataValue(`${value} ${unit}`);
      return;
    }

    if (type === 'time' && !retraining_wait_start_time) {
      setRetrainTimeDataValue(retrainTimeValue);
    }
  }, [
    handleResetData,
    isStopBtn,
    pipelineId,
    retrainTimeValue,
    retraining_config,
    retraining_wait_start_time,
  ]);

  const countRef = useRef(0);
  useEffect(() => {
    if (!retraining_wait_start_time) return;

    countRef.current++;
    if (!countRef.current) return;

    let intervalTimeValue;
    let seconds = 0;

    if (unit === 'hours') seconds = value * 3600;
    if (unit === 'minutes') seconds = value * 60;
    const initialSeconds = seconds;

    intervalTimeValue = setInterval(() => {
      const currentTime = calCurrentTime();
      const diffSecounds = calculateSecondDifference(
        retraining_wait_start_time,
        currentTime,
      );
      const visualTime = initialSeconds - diffSecounds;
      if (visualTime <= 0) {
        clearInterval(intervalTimeValue); // 타이머 종료
        setIntervalValue('-');
        countRef.current = 0;
      } else {
        const intervalValue = calFormatSecondToTime(visualTime);
        setIntervalValue(intervalValue);
      }
    }, 1000);

    return () => {
      clearInterval(intervalTimeValue); // 타이머 종료
      setIntervalValue('-');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unit, value, retraining_wait_start_time]);

  return (
    <ul className={cx('info-list')}>
      {list.map((info) => (
        <Card
          key={info.label}
          icon={info.icon}
          label={info.label}
          value={info.value}
        />
      ))}
      <Card
        key={
          retraining_config.type === 'time'
            ? '재학습까지 남은 시간'
            : '재학습을 위한 데이터 증가량'
        }
        label={
          retraining_config.type === 'time'
            ? '재학습까지 남은 시간'
            : '재학습을 위한 데이터 증가량'
        }
        icon={retraining_config.type === 'time' ? IconDotTime : IconDataset}
        value={
          countRef.current === 0
            ? retrainTimeDataValue
            : intervalRetrainTimeValue
        }
      />
    </ul>
  );
}
