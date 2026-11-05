import React from 'react';
import { shallowEqual, useSelector } from 'react-redux';

import { Badge } from '@jonathan/ui-react';

import PlaygroundFrame from '../../PlaygroundFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './ResourceInfo.module.scss';

const cx = classNames.bind(style);

const calInstanceStatus = (immediately_status) => {
  return {
    color: immediately_status ? '#2D76F8' : '#fa4e57',
    message: immediately_status ? '즉시 사용 가능' : '대기 후 사용 가능',
  };
};

export default function ResourceInfo() {
  const { model, embedding, reranker, immediately_status } = useSelector(
    (state) => state.llmPlayground.info_instance,
    shallowEqual,
  );

  const { color, message } = calInstanceStatus(immediately_status);

  console.log(model);

  return (
    <PlaygroundFrame
      style={{
        border: '1px solid #C8DBFD',
        backgroundColor: '#fff',
      }}
    >
      <div className={cx('title-cont')}>
        <h3 className={cx('title')}>인스턴스 설정 정보</h3>
        <span className={cx('status')} style={{ color }}>
          {message}
        </span>
      </div>
      <div className={cx('resource-wrapper')}>
        {model.instance_name !== '-' && (
          <>
            <div className={cx('resource-cont')}>
              <p className={cx('resource-title')}>모델</p>
              <div className={cx('row-cont')}>
                <div className={cx('left-cont')}>
                  <span className={cx('label-txt')}>인스턴스</span>
                  <span className={cx('instance-value-txt')}>
                    {model.instance_name}
                  </span>
                </div>
                <span className={cx('right-value-txt')}>
                  {model.instance_allocate} EA
                </span>
              </div>
            </div>
            <div className={cx('border')}></div>
            <div className={cx('between-cont')}>
              <div className={cx('left-cont')}>
                <Badge
                  label={model.instance_available ? '여유' : '부족'}
                  size='sm'
                  type={model.instance_available ? 'primary-2' : 'red'}
                  radius='small'
                />
                <span className={cx('label')}>vGPU</span>
              </div>
              <span className={cx('value')}>{model.gpu_allocate} EA</span>
            </div>
            <div className={cx('between-cont')}>
              <div className={cx('left-cont')}>
                <Badge
                  label={model.cpu_available ? '여유' : '부족'}
                  size='sm'
                  type={model.cpu_available ? 'primary-2' : 'red'}
                  radius='small'
                />
                <span className={cx('label')}>vCPU</span>
              </div>
              <span className={cx('value')}>{model.cpu_allocate} Cores</span>
            </div>
            <div className={cx('between-cont')}>
              <div className={cx('left-cont')}>
                <Badge
                  label={model.ram_available ? '여유' : '부족'}
                  size='sm'
                  type={model.ram_available ? 'primary-2' : 'red'}
                  radius='small'
                />
                <span className={cx('label')}>RAM</span>
              </div>
              <span className={cx('value')}>{model.ram_allocate} GB</span>
            </div>
          </>
        )}
        {embedding.instance_name !== '-' && (
          <>
            <div className={cx('resource-border')} />
            <div className={cx('resource-cont')}>
              <p className={cx('resource-title')}>임베딩 모델</p>
              <div className={cx('row-cont')}>
                <div className={cx('left-cont')}>
                  <span className={cx('label-txt')}>인스턴스</span>
                  <span className={cx('instance-value-txt')}>
                    {embedding.instance_name}
                  </span>
                </div>
                <span className={cx('right-value-txt')}>
                  {embedding.instance_count} EA
                </span>
              </div>
              <div className={cx('border')} />
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={embedding.gpu_available ? '여유' : '부족'}
                    size='sm'
                    type={embedding.gpu_available ? 'primary-2' : 'red'}
                    radius='small'
                  />
                  <span className={cx('label')}>vGPU</span>
                </div>
                <span className={cx('value')}>{embedding.gpu_allocate} EA</span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={embedding.cpu_available ? '여유' : '부족'}
                    size='sm'
                    type={embedding.cpu_available ? 'primary-2' : 'red'}
                    radius='small'
                  />
                  <span className={cx('label')}>vCPU</span>
                </div>
                <span className={cx('value')}>
                  {embedding.cpu_allocate} Cores
                </span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={embedding.ram_available ? '여유' : '부족'}
                    size='sm'
                    type={embedding.ram_available ? 'primary-2' : 'red'}
                    radius='small'
                  />
                  <span className={cx('label')}>RAM</span>
                </div>
                <span className={cx('value')}>{embedding.ram_allocate} GB</span>
              </div>
            </div>
          </>
        )}
        {reranker.instance_name !== '-' && (
          <>
            <div className={cx('resource-border')} />
            <div className={cx('resource-cont')}>
              <p className={cx('resource-title')}>리랭커 모델</p>
              <div className={cx('row-cont')}>
                <div className={cx('left-cont')}>
                  <span className={cx('label-txt')}>인스턴스</span>
                  <span className={cx('instance-value-txt')}>
                    {embedding.instance_name}
                  </span>
                </div>
                <span className={cx('right-value-txt')}>
                  {embedding.instance_count} EA
                </span>
              </div>
              <div className={cx('border')} />
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={reranker.gpu_available ? '여유' : '부족'}
                    size='sm'
                    type={reranker.gpu_available ? 'primary-2' : 'red'}
                    radius='small'
                  />
                  <span className={cx('label')}>vGPU</span>
                </div>
                <span className={cx('value')}>{reranker.gpu_allocate} EA</span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={reranker.cpu_available ? '여유' : '부족'}
                    size='sm'
                    type={reranker.cpu_available ? 'primary-2' : 'red'}
                    radius='small'
                  />
                  <span className={cx('label')}>vCPU</span>
                </div>
                <span className={cx('value')}>
                  {reranker.cpu_allocate} Cores
                </span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={reranker.ram_available ? '여유' : '부족'}
                    size='sm'
                    type={reranker.ram_available ? 'primary-2' : 'red'}
                    radius='small'
                  />
                  <span className={cx('label')}>RAM</span>
                </div>
                <span className={cx('value')}>{reranker.ram_allocate} GB</span>
              </div>
            </div>
          </>
        )}
      </div>
    </PlaygroundFrame>
  );
}
