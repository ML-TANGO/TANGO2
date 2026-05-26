import React from 'react';
import { useTranslation } from 'react-i18next';

import dayjs from 'dayjs';

import DashboardFrame from '../DashboardFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardrecentRecord.module.scss';

const cx = classNames.bind(style);

const calTaskMessage = (task) => {
  if (task === 'deployment') return '배포를';
  if (task === 'training') return '학습을';
  if (task === 'workspace') return '워크스페이스를';
  if (task === 'preprocessing') return '전처리 데이터를';
  if (task === 'pipeline') return '파이프라인을';
  console.log('none task type : ', task);
  return 'none task type';
};

const calAction = (action) => {
  if (action === 'delete') return '삭제하였습니다.';
  if (action === 'update') return '업데이트 하였습니다.';
  if (action === 'create') return '생성하였습니다.';
  return 'none action type';
};

const calMessage = (action, task, task_name, user, workspace) => {
  const taskMessage = calTaskMessage(task);
  const actionMessage = calAction(action);
  return `${user}님이 '${workspace}'에서 '${task_name}' ${taskMessage} ${actionMessage}`;
};

export const calDateFormat = (time_stamp) => {
  return dayjs(time_stamp)
    .locale('ko')
    .utcOffset(9)
    .format('YYYY.MM.DD HH:mm:ss');
};

const RecentItem = React.memo(
  ({ idx, action, task, task_name, time_stamp, user, workspace }) => {
    const message = calMessage(action, task, task_name, user, workspace);
    const formatDate = calDateFormat(time_stamp);

    return (
      <li className={cx('content-item')} key={idx}>
        <div className={cx('dot', action)} />
        <div className={cx('content-cont')}>
          <p className={cx('content-para')}>{message}</p>
          <span className={cx('date-txt')}>{formatDate}</span>
        </div>
      </li>
    );
  },
);

const FlagComponent = ({ historyList }) => {
  const { t } = useTranslation();
  if (historyList === null)
    return (
      <div className={cx('center')}>
        <span>{t('noResponse.message')}</span>
      </div>
    );
  return (
    <>
      {historyList.length === 0 && (
        <div className={cx('center')}>
          <span>{t('noRecentTasks.message')}</span>
        </div>
      )}
      <ul className={cx('content-list')}>
        {historyList.map((info, idx) => {
          const { action, task, task_name, time_stamp, user, workspace } = info;
          return (
            <RecentItem
              key={idx}
              action={action}
              task={task}
              task_name={task_name}
              time_stamp={time_stamp}
              user={user}
              workspace={workspace}
            />
          );
        })}
      </ul>
    </>
  );
};

const DashboardrecentRecord = React.memo(({ title, historyList }) => {
  return (
    <DashboardFrame title={title} style={{ height: '560px' }}>
      <FlagComponent historyList={historyList} />
    </DashboardFrame>
  );
});

export default DashboardrecentRecord;
