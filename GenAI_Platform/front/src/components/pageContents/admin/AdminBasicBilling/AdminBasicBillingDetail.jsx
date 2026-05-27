import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './AdminBasicBillingDetail.module.scss';

const cx = classNames.bind(style);

const AdminBasicBillingDetail = ({ data }) => {
  const { t } = useTranslation();
  const {
    add_user_count,
    out_bound_network_usage,
    workspace_manager,
    workspace_name,
    workspace_user_count,
  } = data;

  return (
    <div className={cx('container')}>
      <div className={cx('header')}>{workspace_name}</div>
      <div className={cx('gray-line')}></div>
      <div className={cx('info')}>
        <div className={cx('row')}>
          <div className={cx('type')}>{t('workspaceManager.label')}</div>
          <div className={cx('value')}>{workspace_manager}</div>
        </div>
        <div className={cx('row')}>
          <div className={cx('type')}>{t('workspaceUser')}</div>
          <div className={cx('value')}></div>
        </div>
        <div className={cx('row')}>
          <div className={cx('type')}>{t('currentMemberCount')}</div>
          <div className={cx('value')}>{workspace_user_count} 명</div>
        </div>
        <div className={cx('row')}>
          <div className={cx('type')}>{t('addMemberCount')}</div>
          <div className={cx('value')}>{add_user_count} 명</div>
        </div>
        <div className={cx('row')}>
          <div className={cx('type')}>{t('totalUsageOutBound')}</div>
          <div className={cx('value')}>{out_bound_network_usage} GB</div>
        </div>
      </div>
    </div>
  );
};

export default AdminBasicBillingDetail;
