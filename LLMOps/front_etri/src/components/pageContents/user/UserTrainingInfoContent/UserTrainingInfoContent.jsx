// i18n
import { useTranslation } from 'react-i18next';

import { Button } from '@tango/ui-react';

// Components
import PageTitle from '@src/components/atoms/PageTitle';

import TrainingAuth from './TrainingAuth';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserTrainingInfoContent.module.scss';

const cx = classNames.bind(style);

function UserTrainingInfoContent({
  basicInfo,
  builtInModelInfo,
  instanceInfo,
  accessInfo,
  openDeleteConfirmPopup,
  openEditModal,
}) {
  const { t } = useTranslation();
  const trainingName = basicInfo.name;
  const permissionLevel = accessInfo.permission_level;
  return (
    <div className={cx('training-info-page')}>
      <div className={cx('title-box')}>
        <PageTitle>{trainingName}</PageTitle>
        {permissionLevel && (
          <div className={cx('btn-box')}>
            <Button
              type='secondary'
              onClick={openEditModal}
              disabled={permissionLevel > 3}
            >
              {t('edit.label')}
            </Button>
            <Button
              type='red'
              onClick={openDeleteConfirmPopup}
              disabled={permissionLevel > 3}
            >
              {t('deleteTrainingPopup.title.label')}
            </Button>
          </div>
        )}
      </div>
      {/* <BasicInfo basicInfo={basicInfo} builtInModelInfo={builtInModelInfo} /> */}
      <div className={cx('body')}>
        <TrainingAuth
          accessInfo={accessInfo}
          basicInfo={basicInfo}
          instanceInfo={instanceInfo}
        />
      </div>
    </div>
  );
}

export default UserTrainingInfoContent;
