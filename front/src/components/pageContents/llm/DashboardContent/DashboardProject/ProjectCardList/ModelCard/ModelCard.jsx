import React from 'react';
import { useTranslation } from 'react-i18next';

import { Badge } from '@jonathan/ui-react';

import ModelIcon from '@src/components/icon/ModelIcon';

// CSS Module
import classNames from 'classnames/bind';
import style from './ModelCard.module.scss';

import IconHugginFace from '@src/static/images/icon/hugging-face.svg';

const cx = classNames.bind(style);

const calStatus = (status, t) => {
  if (status === 'running')
    return { color: '#00C775', message: t('llm.dashboard.rag.running.status') };
  if (status === 'installing')
    return { color: '#FF7A00', message: t('llm.dashboard.rag.ready.status') };
  if (status === 'pending')
    return { color: '#FF7A00', message: t('llm.dashboard.rag.setting.status') };
  if (status === 'stop')
    return { color: '#FF7A00', message: t('llm.dashboard.rag.stop.status') };
  return {
    color: '#FF7A00',
    message: t('llm.dashboard.rag.done.status'),
  };
};

export default function ModelCard({ info }) {
  const { t } = useTranslation();

  const {
    name,
    commit_model_name,
    config_files_count,
    datasets_count,
    huggingface_model_id,
    instance,
    status,
    type,
  } = info;
  const {
    cpu_allocate,
    gpu_allocate,
    instance_count,
    instance_name,
    ram_allocate,
    resource_name,
    used_gpu_count,
  } = instance;

  const { color, message } = calStatus(status, t);

  return (
    <div className={cx('wrapper')}>
      <div className={cx('header-cont')}>
        <div className={cx('left-cont')}>
          <Badge label={t('Model')} size='lg' type='orange' />
          <span className={cx('title-txt')}>{name}</span>
        </div>
        <div className={cx('right-cont')}>
          {commit_model_name ? (
            <ModelIcon width={16} height={16} color={'#3E3E3E'} />
          ) : (
            <img src={IconHugginFace} alt='hugging-face-icon' />
          )}
          <span className={cx('img-value-txt')}>
            {commit_model_name ? commit_model_name : huggingface_model_id}
          </span>
        </div>
      </div>
      <div className={cx('border')} />
      <div className={cx('content-cont')}>
        <div className={cx('content-first-cont')}>
          <div className={cx('left-cont')}>
            <div className={cx('label-cont')}>
              <span className={cx('label-txt')}>{t('trainingData.label')}</span>
              <span className={cx('value-txt')}>{datasets_count ?? 0} EA</span>
            </div>
            <div className={cx('label-cont')}>
              <span className={cx('label-txt')}>
                Configuration {t('file.label')}
              </span>
              <span className={cx('value-txt')}>
                {config_files_count ?? 0} EA
              </span>
            </div>
          </div>
          <div className={cx('right-cont')}>
            <span className={cx('label-txt')}>{t('progressStatus')}</span>
            <span className={cx('value-txt')} style={{ color }}>
              {message}
            </span>
          </div>
        </div>
        <div className={cx('content-second-cont')}>
          <div className={cx('left-cont')}>
            <div className={cx('label-cont')}>
              <span className={cx('label-txt')}>{t('instance.label')}</span>
              <span className={cx('value-txt')}>{instance_name ?? '-'}</span>
            </div>
            <div className={cx('instance-cont')}>
              <div className={cx('instance-label-cont')}>
                <span className={cx('label-txt')}>vGPU</span>
                <span className={cx('value-txt')}>
                  {resource_name
                    ? `${resource_name} x ${gpu_allocate} EA`
                    : '-'}
                </span>
              </div>
              <div className={cx('instance-label-cont')}>
                <span className={cx('label-txt')}>vCPU</span>
                <span className={cx('value-txt')}>
                  {cpu_allocate ?? 0} cores
                </span>
              </div>
              <div className={cx('instance-label-cont')}>
                <span className={cx('label-txt')}>RAM</span>
                <span className={cx('value-txt')}>{ram_allocate ?? 0} GB</span>
              </div>
            </div>
          </div>
          <div className={cx('right-cont')}>
            <span className={cx('label-txt')}>{t('gpuAllocation.label')}</span>
            <span className={cx('value-txt')}>{used_gpu_count ?? 0} EA</span>
          </div>
        </div>
      </div>
    </div>
  );
}
