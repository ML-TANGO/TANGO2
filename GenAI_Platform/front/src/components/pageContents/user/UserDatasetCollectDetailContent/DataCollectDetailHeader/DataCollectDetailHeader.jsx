import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import {
  postCollectStart,
  postCollectStop,
} from '@src/apis/flightbase/dataset/collect';
import { STATUS_SUCCESS } from '@src/network';

import { calDataType } from '../../UserDatasetCollectMenuContent/DataCollectCardItem/DataCollectCardItem';

// CSS Module
import classNames from 'classnames/bind';
import style from './DataCollectDetailHeader.module.scss';

const cx = classNames.bind(style);

export const calisStop = (status) => {
  if (['running', 'pending', 'installing'].includes(status)) {
    return true;
  }

  if (['running', 'pending', 'installing'].includes(status?.status)) {
    return true;
  }
  return false;
};

export default function DataCollectDetailHeader({
  isExcuteBtn,
  id,
  name,
  collect_method,
  status,
  getHistoryList,
  getCollectInfoValue,
}) {
  const history = useHistory();
  const { t } = useTranslation();

  const dataType = calDataType(collect_method);
  const isStopBtn = calisStop(status);

  const handleHistoryBack = useCallback(() => {
    history.goBack(-1);
  }, [history]);

  const [isLoading, setIsLoading] = useState(false);
  const handleStart = useCallback(
    async (id) => {
      if (isLoading) return;
      setIsLoading(true);
      const { message, status } = await postCollectStart(+id);
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      } else {
        await getHistoryList();
        await getCollectInfoValue();
      }
      setIsLoading(false);
    },
    [getCollectInfoValue, getHistoryList, isLoading],
  );

  const handleStop = useCallback(
    async (id) => {
      if (isLoading) return;
      setIsLoading(true);
      const { message, status } = await postCollectStop(+id);
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      } else {
        await getHistoryList();
        await getCollectInfoValue();
      }
      setIsLoading(false);
    },
    [getCollectInfoValue, getHistoryList, isLoading],
  );

  return (
    <div className={cx('header-cont')}>
      <button className={cx('back-btn')} onClick={handleHistoryBack}>
        <img
          src='/src/static/images/icon/00-ic-basic-arrow-02-left.svg'
          alt='back-icon'
          loading='lazy'
        />
        <span>데이터 수집</span>
      </button>
      <div className={cx('title-wrapper')}>
        <div className={cx('title-cont')}>
          <h1 className={cx('title')}>{name}</h1>
          <span>{dataType}</span>
        </div>
        <div className={cx('flex-cont')}>
          {isStopBtn && (
            <p className={cx('message')}>
              현재 데이터 수집이 진행 중입니다. 설정을 수정하시려면, 실행을
              중지한 후 변경해 주세요.
            </p>
          )}
          {isExcuteBtn && (
            <ButtonV2
              isLoading={isLoading}
              label={isStopBtn ? t('stop') : t('run.label')}
              colorType={isStopBtn ? 'red' : 'blue'}
              onClick={isStopBtn ? () => handleStop(id) : () => handleStart(id)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
