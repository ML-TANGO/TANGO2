// i18n
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
// CSS Module
import style from './AdminGroupDetail.module.scss';

const cx = classNames.bind(style);

const AdminGroupDetail = ({ name, description, userNameList }) => {
  const { t } = useTranslation();
  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <span className={cx('id-txt')}>{name}</span>
        <span className={cx('title-txt')}>
          {t('detailsOf.label', { name: '' })}
        </span>
      </div>
      <p className={cx('desc')}>{description || '-'}</p>
      <span className={cx('user-list-txt')}>{t('userList.label')}</span>
      <div className={cx('user-list-cont')}>{userNameList.join(', ')}</div>
    </div>
  );
};

export default AdminGroupDetail;
