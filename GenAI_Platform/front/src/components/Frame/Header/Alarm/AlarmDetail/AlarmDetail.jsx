import { memo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';
import { useHistory } from 'react-router-dom';

import FBLoading from '@src/components/organisms/FBLoading';

import useOutsideClick from '@src/hooks/useOutsideClick';
import usePreventDoubleClick from '@src/hooks/usePreventDoubleClick';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage, executeWithLogging } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AlarmDetail.module.scss';

import DeleteIcon from '@src/static/images/icon/00-ic-close-gray.svg';

const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();

const NOTI_ADMIN_TYPE_PATH = {
  user: '/admin/users',
  workspace: '/admin/workspaces',
};

const NOTI_USER_TYPE_PATH = {
  user: '/user/dashboard',
  workspace: '/user/dashboard',
};

const formatKoreanDateTime = (isoDateTime, t) => {
  // ISO 8601 문자열을 Date 객체로 변환
  const date = new Date(isoDateTime + 'Z'); // 'Z'를 추가하여 UTC로 해석

  const now = new Date();
  const past = new Date(date);

  const month = past.getMonth() + 1;
  const day = past.getDate();
  const korDate = `${month}${t('month.label')} ${day}${t('day.label')}`;

  // 시간 차이 계산 (밀리초 단위)
  const timeDifference = now - past;

  // 밀리초를 시간으로 변환
  const hoursDifference = Math.floor(timeDifference / (1000 * 60 * 60));

  return { hoursDifference, korDate };
};

const caldateMessage = (hoursDifference, korDate, t) => {
  if (hoursDifference === 0) return t('before.justMoment.label');
  if (hoursDifference < 24)
    return t('before.hour.label', { hour: hoursDifference });
  return korDate;
};

const AlarmItem = memo(({ info, isLoading, getAlarmList, t }) => {
  const history = useHistory();
  const { _id, read, message, create_datetime } = info;
  const { type: userType } = useSelector((state) => state.auth, shallowEqual);
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const handleAlarmRead = useCallback(
    async (isLoading, userName, userType, info) => {
      if (isLoading.current) return;

      // ** 타입 마다 해당 페이지로 이동 **
      const { noti_type, read, _id } = info;
      if (userType === 'USER') {
        history.push(NOTI_USER_TYPE_PATH[noti_type]);
      }

      if (userType === 'ADMIN') {
        history.push(NOTI_ADMIN_TYPE_PATH[noti_type]);
      }

      // ** 읽지 않은 알림 읽음 처리 **
      if (read === 0) {
        isLoading.current = true;
        await executeWithLogging(async () => {
          const { status } = await callApi({
            url: 'notification/read',
            method: 'post',
            body: {
              user_name: userName,
              notification_id: _id,
            },
          });
          if (status === STATUS_SUCCESS) {
            getAlarmList();
          }
        });
      }
    },
    [getAlarmList, history],
  );

  const handleDeleteAlarm = async (e) => {
    e.stopPropagation();
    if (isLoading.current) return;
    isLoading.current = true;

    await executeWithLogging(async () => {
      const { status, error, errorMessage } = await callApi({
        url: 'notification',
        method: 'delete',
        body: {
          notification_id: _id,
        },
      });

      if (status === STATUS_SUCCESS) {
        console.log('alarm delete success');
        getAlarmList();
      } else {
        errorToastMessage(error, errorMessage);
      }
    });
  };
  const handlePreventDoubleDelete = usePreventDoubleClick(
    handleDeleteAlarm,
    1000,
  );

  const { hoursDifference, korDate } = formatKoreanDateTime(
    create_datetime.split('.')[0],
    t,
  );

  return (
    <li
      key={_id}
      className={cx(
        'alarm-item',
        read === 0 ? 'not-read' : 'read',
        isLoading.current && 'loading',
      )}
      onClick={() => handleAlarmRead(isLoading, userName, userType, info)}
    >
      <div className={cx('flex-cont')}>
        {isLoading.current && (
          <div className={cx('loading-cont')}>
            <FBLoading />
          </div>
        )}
        <div className={cx('dot', read !== 0 && 'read')} />
        <div className={cx('contents-cont')}>
          <p className={cx('alarm-message')}>{message}</p>
          <span className={cx('time-txt')}>
            {caldateMessage(hoursDifference, korDate, t)}
          </span>
        </div>
        {!isLoading.current && (
          <img
            className={cx('delete-btn')}
            onClick={(e) => handlePreventDoubleDelete(e)}
            src={DeleteIcon}
            alt='deleteIcon'
          />
        )}
      </div>
      <div className={cx('border')}></div>
    </li>
  );
});

const AlarmDetail = ({
  isLoading,
  alarmList,
  handleAlarmToggle,
  getAlarmList,
}) => {
  const { t } = useTranslation();
  const { ref } = useOutsideClick(handleAlarmToggle);

  const handleAllReadAlarm = async (isLoading, alarmList) => {
    if (isLoading.current) return;

    const isAlarmNoneRead = alarmList.find((info) => info.read === 0);
    if (!isAlarmNoneRead) return;

    isLoading.current = true;
    executeWithLogging(async () => {
      const { status } = await callApi({
        url: 'notification/read-all',
        method: 'post',
      });
      if (status === STATUS_SUCCESS) {
        getAlarmList();
      }
    });
  };

  const handleAllDelete = async (isLoading, alarmList) => {
    if (!alarmList.length) return;
    if (isLoading.current) return;

    isLoading.current = true;
    executeWithLogging(async () => {
      const { status } = await callApi({
        url: 'notification/all',
        method: 'delete',
      });
      if (status === STATUS_SUCCESS) {
        getAlarmList();
      }
    });
  };

  return (
    <div
      ref={ref}
      className={cx('detail-cont', MODE !== 'integration' && 'small')}
    >
      <div className={cx('alarm-header')}>
        <h1 className={cx('alarm-title')}>{t('alarm.label')}</h1>
        <div className={cx('btn-list')}>
          <button
            className={cx('read-btn')}
            onClick={() => handleAllReadAlarm(isLoading, alarmList)}
          >
            {t('allread.btn')}
          </button>
          <button
            className={cx('delete-btn')}
            onClick={() => handleAllDelete(isLoading, alarmList)}
          >
            {t('alldelete.btn')}
          </button>
        </div>
      </div>
      <ul className={cx('alarm-list')}>
        {alarmList.length === 0 && (
          <div className={cx('no-alarm-cont')}>
            <p className={cx('no-alarm')}>{t('no.alarm.label')}</p>
          </div>
        )}
        {alarmList.length > 0 &&
          alarmList.map((info) => {
            return (
              <AlarmItem
                key={info._id}
                info={info}
                isLoading={isLoading}
                getAlarmList={getAlarmList}
                t={t}
              />
            );
          })}
      </ul>
    </div>
  );
};

export default AlarmDetail;
