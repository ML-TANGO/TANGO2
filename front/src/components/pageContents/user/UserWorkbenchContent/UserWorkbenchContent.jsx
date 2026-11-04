// Components
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRouteMatch } from 'react-router-dom';

import { callApi, STATUS_SUCCESS } from '@src/network';

import IntegratedTool from './IntegratedTool';
import QueueTool from './QueueTool';
import UserWorkbenchHeader from './UserWorkbenchHeader';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserWorkbenchContent.module.scss';

const cx = classNames.bind(style);

const initialTrainInfo = {
  trainType: '',
  trainName: '',
};

function UserWorkbenchContent() {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { tid } = match.params;

  const [traingInfo, setTrainingInfo] = useState(initialTrainInfo);
  const { trainType, trainName } = traingInfo;

  useEffect(() => {
    //  ** Training Info 받기 위한 함수
    const getTrainingInfo = async (tid, setTrainingInfo) => {
      const { status, result, message, error } = await callApi({
        url: `projects/detail/${tid}`,
        method: 'GET',
      });

      if (status === STATUS_SUCCESS) {
        setTrainingInfo({
          trainType: result.type,
          trainName: result.name,
        });
      } else {
        errorToastMessage(error, message);
      }
    };

    getTrainingInfo(tid, setTrainingInfo);
  }, [tid]);

  return (
    <div className={cx('content')}>
      <UserWorkbenchHeader trainingName={trainName} t={t} />
      <QueueTool />
      {trainType === 'advanced' && <IntegratedTool trainingType={trainType} />}
    </div>
  );
}

export default UserWorkbenchContent;
