import React from 'react';
import { useTranslation } from 'react-i18next';

import { Badge } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './PlaygroundCard.module.scss';

const cx = classNames.bind(style);

const calStatus = (status, t) => {
  if (status === 'running') return { color: '#2D76F8', message: t('running') };
  if (status === 'installing')
    return { color: '#FF7A00', message: t('installing') };
  if (status === 'pending')
    return { color: '#FF7A00', message: t('deactivated.label') };
  if (status === 'stop') return { color: '#FF7A00', message: t('stop') };
  return {
    color: '#FF7A00',
    message: t('complete'),
  };
};

export default function PlaygroundCard({ info }) {
  const { t } = useTranslation();
  const { status, name, instance } = info;
  const { embedding, playground, reranker } = instance;

  const { color, message } = calStatus(status, t);

  return (
    <div className={cx('wrapper')}>
      <div className={cx('header-cont')}>
        <div className={cx('left-cont')}>
          <Badge label={t('playground.label')} size='lg' type='primary-2' />
          <span className={cx('title-txt')}>{name}</span>
        </div>
        <div className={cx('right-cont')}>
          <span className={cx('label-txt')}>{t('Deploy.status')}</span>
          <span className={cx('value-txt')} style={{ color }}>
            {message}
          </span>
        </div>
      </div>
      {(playground || embedding || reranker) && (
        <div className={cx('border')} />
      )}
      {playground && (
        <div className={cx('content-cont')}>
          <div className={cx('content-first-cont')}>
            <span className={cx('label-txt')}>{t('Model')}</span>
            <span className={cx('value-txt')}>
              {playground.model_name ?? '-'}
            </span>
          </div>
          <div className={cx('content-second-cont')}>
            <div className={cx('left-cont')}>
              <div className={cx('instance-cont')}>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>vGPU</span>
                  <span className={cx('value-txt')}>
                    {playground.resource_name
                      ? `${playground.resource_name} x ${
                          playground.gpu_allocate ?? 0
                        } EA`
                      : '-'}
                  </span>
                </div>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>vCPU</span>
                  <span className={cx('value-txt')}>
                    {playground.cpu_allocate ?? 0} cores
                  </span>
                </div>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>RAM</span>
                  <span className={cx('value-txt')}>
                    {playground.ram_allocate ?? 0} GB
                  </span>
                </div>
              </div>
            </div>
            <div className={cx('right-cont')}>
              <span className={cx('label-txt')}>
                {t('gpuAllocation.label')}
              </span>
              <span className={cx('value-txt')}>
                {playground.used_gpu_count ?? 0} EA
              </span>
            </div>
          </div>
        </div>
      )}
      {embedding && (
        <div className={cx('content-cont')}>
          <div className={cx('content-first-cont')}>
            <span className={cx('label-txt')}>{t('Rag.inbedding.model')}</span>
            <span className={cx('value-txt')}>
              {embedding.model_name ?? '-'}
            </span>
          </div>
          <div className={cx('content-second-cont')}>
            <div className={cx('left-cont')}>
              <div className={cx('instance-cont')}>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>vGPU</span>
                  <span className={cx('value-txt')}>
                    {embedding.resource_name} x {embedding.gpu_allocate ?? 0} EA
                  </span>
                </div>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>vCPU</span>
                  <span className={cx('value-txt')}>
                    {embedding.cpu_allocate} cores
                  </span>
                </div>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>RAM</span>
                  <span className={cx('value-txt')}>
                    {embedding.ram_allocate} GB
                  </span>
                </div>
              </div>
            </div>
            <div className={cx('right-cont')}>
              <span className={cx('label-txt')}>
                {t('gpuAllocation.label')}
              </span>
              <span className={cx('value-txt')}>
                {embedding.used_gpu_count} EA
              </span>
            </div>
          </div>
        </div>
      )}
      {reranker && (
        <div className={cx('content-cont')}>
          <div className={cx('content-first-cont')}>
            <span className={cx('label-txt')}>{t('Rag.reranker.model')}</span>
            <span className={cx('value-txt')}>
              {reranker.instance_name ?? '-'}
            </span>
          </div>
          <div className={cx('content-second-cont')}>
            <div className={cx('left-cont')}>
              <div className={cx('instance-cont')}>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>vGPU</span>
                  <span className={cx('value-txt')}>
                    {reranker.resource_name} x {reranker.gpu_allocate ?? 0} EA
                  </span>
                </div>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>vCPU</span>
                  <span className={cx('value-txt')}>
                    {reranker.cpu_allocate} cores
                  </span>
                </div>
                <div className={cx('instance-label-cont')}>
                  <span className={cx('label-txt')}>RAM</span>
                  <span className={cx('value-txt')}>
                    {reranker.ram_allocate} GB
                  </span>
                </div>
              </div>
            </div>
            <div className={cx('right-cont')}>
              <span className={cx('label-txt')}>
                {t('gpuAllocation.label')}
              </span>
              <span className={cx('value-txt')}>
                {reranker.used_gpu_count} EA
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
