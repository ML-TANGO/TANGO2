import React from 'react';
import { useTranslation } from 'react-i18next';

import { StatusCard, Tooltip } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './InstanceSetting.module.scss';

const cx = classNames.bind(style);

const initialData = {
  instance: {},
};
export default function InstanceSetting({ infoData }) {
  const { t } = useTranslation();

  const instance = infoData ?? initialData;

  return (
    <div className={cx('container')}>
      <div className={cx('flex-32')}>
        <div className={cx('title-cont')}>
          <h3>{`${t('instanceSetting.label')} ${t('information.label')}`}</h3>
          <span style={{ color: instance.instance_available ? '#2d76f8' : '' }}>
            {instance.instance_available
              ? t('immediatelyAvailable.label')
              : t('pendingApproval')}
          </span>
          {/* <Tooltip /> */}
        </div>
        <div className={cx('flex-16')}>
          <div className={cx('between-cont')}>
            <div className={cx('left-cont')}>
              <span className={cx('label')}>{t('Instance')}</span>
              <span className={cx('value')}>{instance.instance_name}</span>
            </div>
            <span className={cx('value')}>
              {instance.instance_allocate
                ? `${instance.instance_allocate} EA`
                : '-'}
            </span>
          </div>
          <div className={cx('border')}></div>
          {/* <div className={cx('between-cont')}>
            <span className={cx('label')}>vGPU</span>
            <span className={cx('value')}>1 EA</span>
          </div> */}
          <div className={cx('between-cont')}>
            <div className={cx('label')}>
              <StatusCard
                status={instance.gpu_available ? 'blue' : 'red'}
                text={instance.gpu_available ? t('idle.label') : t('low.label')}
                size='x-small'
              />
              vGPU
            </div>
            <span className={cx('value')}>
              {instance.gpu_allocate ? `${instance.gpu_allocate} EA` : '-'}
            </span>
          </div>
          <div className={cx('between-cont')}>
            <div className={cx('label')}>
              <StatusCard
                status={instance.cpu_available ? 'blue' : 'red'}
                text={instance.cpu_available ? t('idle.label') : t('low.label')}
                size='x-small'
              />
              vCPU
            </div>
            <span className={cx('value')}>
              {instance.cpu_allocate ? `${instance.cpu_allocate} Cores` : '-'}
            </span>
          </div>
          <div className={cx('between-cont')}>
            <div className={cx('label')}>
              <StatusCard
                status={instance.ram_available ? 'blue' : 'red'}
                text={instance.ram_available ? t('idle.label') : t('low.label')}
                size='x-small'
              />
              RAM
            </div>
            <span className={cx('value')}>
              {instance.ram_allocate ? `${instance.ram_allocate} GB` : '-'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
