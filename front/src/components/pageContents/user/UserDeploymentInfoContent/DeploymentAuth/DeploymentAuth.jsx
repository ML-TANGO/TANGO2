// i18n
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeploymentAuth.module.scss';
const cx = classNames.bind(style);

function DeploymentAuth({ accessInfo }) {
  const { t } = useTranslation();
  const { access, owner, user_list: userList } = accessInfo;
  return (
    <div className={cx('deployment-auth')}>
      <div className={cx('header')}>
        <span className={cx('title')}>{t('accessSettings.title.label')}</span>
        <div className={cx('btn-wrap')}></div>
      </div>
      <div className={cx('content')}>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('accessType.label')}</div>
          <div className={cx('value')}>
            {access === 1 ? 'public' : 'private'}
          </div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('owner.label')}</div>
          <div className={cx('value')}>{owner || '-'}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('user.label')}</div>
          <div className={cx('value')}>
            {userList && userList.length > 0
              ? userList.map((u) => u.user_name).join(', ')
              : '-'}
          </div>
        </div>
      </div>
    </div>
  );
}

export default DeploymentAuth;
