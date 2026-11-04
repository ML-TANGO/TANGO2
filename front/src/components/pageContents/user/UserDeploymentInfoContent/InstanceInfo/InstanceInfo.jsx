import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './InstanceInfo.module.scss';

const cx = classNames.bind(style);

const InstanceInfo = ({ instanceInfo }) => {
  const { t } = useTranslation();

  return (
    <div className={cx('basic-info')}>
      <div className={cx('header')}>
        <span className={cx('title')}>{t('instanceSetting.label')}</span>
      </div>
      <div className={cx('content')}>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('instanceName.label')}</div>
          <div className={cx('value')}>{instanceInfo.instance_name ?? '-'}</div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>{t('instanceCount.label')}</div>
          <div className={cx('value')}>
            {instanceInfo.instance_allocate ?? '-'}
          </div>
        </div>
        <div className={cx('header')}>
          <span className={cx('title')}>
            {t('instanceConfiguration.label')}
          </span>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>vGPU</div>
          <div className={cx('value')}>
            {instanceInfo.config_gpu_name
              ? `${instanceInfo.config_gpu_name} x ${instanceInfo.config_gpu_allocate}EA`
              : '-'}
          </div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>vCPU</div>
          <div className={cx('value')}>
            {`${instanceInfo.config_vcpu ?? ''} Cores`}
          </div>
        </div>
        <div className={cx('item')}>
          <div className={cx('label')}>RAM</div>
          <div className={cx('value')}>{`${
            instanceInfo.config_ram ?? ''
          } GB`}</div>
        </div>
      </div>
    </div>
  );
};

export default InstanceInfo;
