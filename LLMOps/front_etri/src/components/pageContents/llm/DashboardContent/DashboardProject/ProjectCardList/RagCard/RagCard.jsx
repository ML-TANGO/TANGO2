import React from 'react';
import { useTranslation } from 'react-i18next';

import { Badge } from '@tango/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './RagCard.module.scss';

const cx = classNames.bind(style);

const calStatus = (status, t) => {
  if (['running', 'installing'].includes(status))
    return { color: '#FF7A00', message: t('running.docs.status') };
  if (status === 'pending') return { color: '#FF7A00', message: t('stop') };
  if (status === 'stop') return { color: '#FF7A00', message: t('stop') };
  return {
    color: '',
    message: '',
  };
};

export default function RagCard({ info }) {
  const { t } = useTranslation();
  const { name, model, status, instance } = info;
  const { rag_embedding, rag_reranker, test_embedding, test_reranker } =
    instance;
  const { embedding, reranker } = model;
  const { rag: ragStatus, test: testStatus } = status;

  const { message: message1, color: color1 } = calStatus(ragStatus, t);
  const { message: message2, color: color2 } = calStatus(testStatus, t);

  return (
    <div className={cx('wrapper')}>
      <div className={cx('header-cont')}>
        <div className={cx('left-cont')}>
          <Badge label='RAG' size='lg' type='green' />
          <span className={cx('title-txt')}>{name}</span>
        </div>
        <div className={cx('right-cont')}>
          {message1 && (
            <div className={cx('label-cont')}>
              <span className={cx('label-txt')}>{t('create.status')}</span>
              <span className={cx('value-txt')} style={{ color: color1 }}>
                {message1}
              </span>
            </div>
          )}
          {message2 && (
            <div className={cx('label-cont')}>
              <span className={cx('label-txt')}>{t('test.status')}</span>
              <span className={cx('value-txt')} style={{ color: color2 }}>
                {message2}
              </span>
            </div>
          )}
        </div>
      </div>
      {embedding && reranker && <div className={cx('border')} />}
      {embedding && (
        <div className={cx('content-cont')}>
          <div className={cx('content-first-cont')}>
            <span className={cx('label-txt')}>
              {t('ragEmbeddedModel.label')}
            </span>
            <span className={cx('value-txt')}>{embedding ?? '-'}</span>
          </div>
          {rag_embedding && (
            <div className={cx('content-second-cont')}>
              <div className={cx('left-cont')}>
                <div className={cx('label-cont')}>
                  <span className={cx('label-txt')}>
                    {t('create.instance.label')}
                  </span>
                  <span className={cx('value-txt')}>
                    {rag_embedding.instance_name
                      ? `${rag_embedding.instance_name} x ${rag_embedding.instance_count} EA`
                      : '-'}
                  </span>
                </div>
                <div className={cx('instance-cont')}>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vGPU</span>
                    <span className={cx('value-txt')}>
                      {rag_embedding.resource_name
                        ? `${rag_embedding.resource_name} x ${rag_embedding.gpu_allocate} EA`
                        : '-'}
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vCPU</span>
                    <span className={cx('value-txt')}>
                      {rag_embedding.cpu_allocate ?? 0} cores
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>RAM</span>
                    <span className={cx('value-txt')}>
                      {rag_embedding.ram_allocate ?? 0} GB
                    </span>
                  </div>
                </div>
              </div>
              <div className={cx('right-cont')}>
                <span className={cx('label-txt')}>
                  {t('gpuAllocation.label')}
                </span>
                <span className={cx('value-txt')}>
                  {rag_embedding.used_gpu_count ?? 0} EA
                </span>
              </div>
            </div>
          )}
          {test_embedding && (
            <div className={cx('content-second-cont')}>
              <div className={cx('left-cont')}>
                <div className={cx('label-cont')}>
                  <span className={cx('label-txt')}>
                    {t('create.instance.label')}
                  </span>
                  <span className={cx('value-txt')}>
                    {test_embedding.resource_name
                      ? `${test_embedding.resource_name} x ${test_embedding.gpu_allocate} EA`
                      : '-'}
                  </span>
                </div>
                <div className={cx('instance-cont')}>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vGPU</span>
                    <span className={cx('value-txt')}>
                      {test_embedding.resource_name
                        ? `${test_embedding.resource_name} x ${test_embedding.gpu_allocate} EA`
                        : '-'}
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vCPU</span>
                    <span className={cx('value-txt')}>
                      {test_embedding.cpu_allocate ?? 0} cores
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>RAM</span>
                    <span className={cx('value-txt')}>
                      {test_embedding.ram_allocate ?? 0} GB
                    </span>
                  </div>
                </div>
              </div>
              <div className={cx('right-cont')}>
                <span className={cx('label-txt')}>
                  {t('gpuAllocation.label')}
                </span>
                <span className={cx('value-txt')}>
                  {test_embedding.used_gpu_count ?? 0} EA
                </span>
              </div>
            </div>
          )}
        </div>
      )}
      {reranker && (
        <div className={cx('content-cont')}>
          <div className={cx('content-first-cont')}>
            <span className={cx('label-txt')}>
              {t('llm.rag.reRanker.label')}
            </span>
            <span className={cx('value-txt')}>{reranker}</span>
          </div>
          {rag_reranker && (
            <div className={cx('content-second-cont')}>
              <div className={cx('left-cont')}>
                <div className={cx('label-cont')}>
                  <span className={cx('label-txt')}>
                    {t('create.instance.label')}
                  </span>
                  <span className={cx('value-txt')}>
                    {rag_reranker.instance_name}
                  </span>
                </div>
                <div className={cx('instance-cont')}>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vGPU</span>
                    <span className={cx('value-txt')}>
                      {rag_reranker.resource_name} x {rag_reranker.gpu_allocate}{' '}
                      EA
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vCPU</span>
                    <span className={cx('value-txt')}>
                      {rag_reranker.cpu_allocate} cores
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>RAM</span>
                    <span className={cx('value-txt')}>
                      {rag_reranker.ram_allocate} GB
                    </span>
                  </div>
                </div>
              </div>
              <div className={cx('right-cont')}>
                <span className={cx('label-txt')}>
                  {t('gpuAllocation.label')}
                </span>
                <span className={cx('value-txt')}>
                  {rag_reranker.used_gpu_count} EA
                </span>
              </div>
            </div>
          )}
          {test_reranker && (
            <div className={cx('content-second-cont')}>
              <div className={cx('left-cont')}>
                <div className={cx('label-cont')}>
                  <span className={cx('label-txt')}>
                    {t('test.instance.label')}
                  </span>
                  <span className={cx('value-txt')}>
                    {test_reranker.instance_name}
                  </span>
                </div>
                <div className={cx('instance-cont')}>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vGPU</span>
                    <span className={cx('value-txt')}>
                      {test_reranker.resource_name} x{' '}
                      {test_reranker.gpu_allocate} EA
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>vCPU</span>
                    <span className={cx('value-txt')}>
                      {test_reranker.cpu_allocate} cores
                    </span>
                  </div>
                  <div className={cx('instance-label-cont')}>
                    <span className={cx('label-txt')}>RAM</span>
                    <span className={cx('value-txt')}>
                      {test_reranker.ram_allocate} GB
                    </span>
                  </div>
                </div>
              </div>
              <div className={cx('right-cont')}>
                <span className={cx('label-txt')}>
                  {t('gpuAllocation.label')}
                </span>
                <span className={cx('value-txt')}>
                  {test_reranker.used_gpu_count} EA
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
