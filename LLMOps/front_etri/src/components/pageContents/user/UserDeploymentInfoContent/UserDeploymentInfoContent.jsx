// i18n
import { useTranslation } from 'react-i18next';

// Components
import PageTitle from '@src/components/atoms/PageTitle';
import BasicInfo from './BasicInfo';
import DeploymentAuth from './DeploymentAuth';
import UsageStatus from './UsageStatus';
import DeploymentLog from './DeploymentLog';
import InstanceInfo from './InstanceInfo';
import { Button } from '@tango/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserDeploymentInfoContent.module.scss';
const cx = classNames.bind(style);

function UserDeploymentInfoContent({
  basicInfo,
  builtInModelInfo,
  accessInfo,
  usageStatusInfo,
  openDeleteConfirmPopup,
  openEditModal,
  openDownloadLogModal,
  openDeleteLogModal,
  openEditApiModal,
  instanceInfo,
}) {
  const { t } = useTranslation();
  const deploymentName = basicInfo.name;
  const permissionLevel = accessInfo.permission_level;
  return (
    <div className={cx('deployment-info-page')}>
      <div className={cx('title-box')}>
        <PageTitle>{deploymentName}</PageTitle>
        {permissionLevel && (
          <div className={cx('btn-box')}>
            <Button
              type='secondary'
              onClick={openEditModal}
              disabled={permissionLevel > 4}
            >
              {t('edit.label')}
            </Button>
            <Button
              type='red'
              onClick={openDeleteConfirmPopup}
              disabled={permissionLevel > 3}
            >
              {t('deleteDeploymentPopup.title.label')}
            </Button>
          </div>
        )}
      </div>
      <BasicInfo
        basicInfo={basicInfo}
        builtInModelInfo={builtInModelInfo}
        openDeleteConfirmPopup={openDeleteConfirmPopup}
        openEditModal={openEditModal}
      />
      <InstanceInfo instanceInfo={instanceInfo} />
      <DeploymentAuth accessInfo={accessInfo} />
      <UsageStatus
        usageStatusInfo={usageStatusInfo}
        permissionLevel={permissionLevel}
        openEditApiModal={openEditApiModal}
      />
      <DeploymentLog
        logInfo={usageStatusInfo}
        permissionLevel={permissionLevel}
        openDownloadLogModal={openDownloadLogModal}
        openDeleteLogModal={openDeleteLogModal}
      />
    </div>
  );
}

export default UserDeploymentInfoContent;
