import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './RagInstance.module.scss';

const cx = classNames.bind(style);

function RagInstance({ instanceInfo }) {
  const { t } = useTranslation();
  const { embedding, reranker } = instanceInfo ?? {
    embedding: null,
    reranker: null,
  };
  return (
    <div className={cx('container')}>
      <div className={cx('title')}>{t('fineTuningResourceAlloc.label')}</div>
      <div className={cx('type')}>
        <div className={cx('label')}>
          <div className={cx('instance')}>{t('ragEmbeddedModel.label')}</div>
        </div>
      </div>
      <div className={cx('gpu-box')}>
        <div className={cx('label')}>
          <div>{t('Instance')}</div>
          <div>{embedding ? embedding.name : '-'}</div>
        </div>
        <div className={cx('value')}>
          {embedding ? embedding.instance_allocate : '0'} EA
        </div>
      </div>
      <div className={cx('gpu-box')}>
        <div className={cx('label')}>
          <div>{t('gpuAllocation.label')}</div>
        </div>
        <div className={cx('value')}>
          {embedding ? embedding.gpu_allocate : '0'} EA
        </div>
      </div>
      {reranker && (
        <>
          <div className={cx('border')} />
          <div className={cx('type')}>
            <div className={cx('label')}>
              <div className={cx('instance')}>
                {t('ragRerankerModel.label')}
              </div>
            </div>
          </div>
          <div className={cx('gpu-box')}>
            <div className={cx('label')}>
              <div>{t('Instance')}</div>
              <div>{reranker.name ?? '-'}</div>
            </div>
            <div className={cx('value')}>
              {reranker.instance_allocate ?? '0'} EA
            </div>
          </div>
          <div className={cx('gpu-box')}>
            <div className={cx('label')}>
              <div>{t('gpuAllocation.label')}</div>
            </div>
            <div className={cx('value')}>{reranker.gpu_allocate ?? '0'} EA</div>
          </div>
        </>
      )}
    </div>
  );
}

export default RagInstance;
