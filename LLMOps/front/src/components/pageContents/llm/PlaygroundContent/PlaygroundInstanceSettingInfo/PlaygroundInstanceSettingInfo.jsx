import React from 'react';
import { shallowEqual, useSelector } from 'react-redux';

import { Badge } from '@jonathan/ui-react';

import PlaygroundFrame from '../PlaygroundFrame';

import classNames from 'classnames/bind';
import style from './PlaygroundInstanceSettingInfo.module.scss';

const cx = classNames.bind(style);

const calInstanceStatus = (model, immediately_status) => {
  if (model.instance_name === '-') return { color: '#fff', message: '' };
  if (!model.instance_name) return { color: '#fff', message: '' };

  return {
    color: immediately_status ? '#2D76F8' : '#fa4e57',
    message: immediately_status ? '즉시 사용 가능' : '대기 후 사용 가능',
  };
};

export default function PlaygroundInstanceSettingInfo({
  model: modelProp,
  status,
  immediatelyStatus,
  allocations,
  title = '인스턴스 설정 정보',
}) {
  const {
    model: reduxModel,
    immediately_status: reduxImmediatelyStatus,
  } = useSelector(
    (state) => state.llmPlayground.info_instance,
    shallowEqual,
  );
  const { status: reduxStatus } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  // props가 없으면 단일 배포의 Redux 값을 그대로 사용한다.
  // dual만 정규화 read-model을 주입해 역할별 상태가 서로 섞이지 않게 한다.
  const model = modelProp ?? reduxModel;
  const statusType = status ?? reduxStatus;
  const isImmediatelyAvailable =
    immediatelyStatus ?? reduxImmediatelyStatus;

  const { color, message } = calInstanceStatus(
    model,
    isImmediatelyAvailable,
  );
  const frameDisabled =
    status === undefined
      ? undefined
      : ['installing', 'pending'].includes(statusType);

  return (
    <PlaygroundFrame
      disabled={frameDisabled}
      style={{ backgroundColor: '#fff' }}
    >
      <div className={cx('header')}>
        <h3 className={cx('title')}>{title}</h3>
        <span className={cx('status')} style={{ color }}>
          {message}
        </span>
      </div>
      <div className={cx('resource-wrapper')}>
        {statusType === '-' && (
          <div className={cx('empty-cont')}>
            <p className={cx('txt')}>배포 자원을 설정하시면</p>
            <p className={cx('txt')}>설정 정보가 화면에 표시됩니다.</p>
          </div>
        )}
        {model.instance_name !== '-' && (
          <>
            <div className={cx('resource-cont')}>
              <p className={cx('resource-title')}>모델</p>
              <div className={cx('row-cont')}>
                <div className={cx('left-cont')}>
                  <span className={cx('label-txt')}>인스턴스</span>
                  <span className={cx('instance-value-txt')}>
                    {model.instance_name ?? '-'}
                  </span>
                </div>
                <span className={cx('right-value-txt')}>
                  {model.instance_allocate
                    ? `${model.instance_allocate} EA`
                    : '0 EA'}
                </span>
              </div>
            </div>
            <div className={cx('border')}></div>
            <div className={cx('between-cont')}>
              <div className={cx('left-cont')}>
                <Badge
                  label={model.gpu_available ? '여유' : '부족'}
                  size='sm'
                  type={model.gpu_available ? 'primary-2' : 'red'}
                  radius='small'
                />
                <span className={cx('label')}>vGPU</span>
              </div>
              <span className={cx('value')}>
                {model.gpu_allocate ? `${model.gpu_allocate} EA` : '0 EA'}
              </span>
            </div>
            {allocations?.map(({ role, gpuCount, badgeType = 'gray' }) => (
              <div className={cx('between-cont')} key={role}>
                <div className={cx('left-cont')}>
                  <Badge
                    label={role}
                    size='sm'
                    type={badgeType}
                    radius='small'
                  />
                  <span className={cx('label')}>GPU 할당</span>
                </div>
                <span className={cx('value')}>
                  {gpuCount != null ? `${gpuCount} EA` : '-'}
                </span>
              </div>
            ))}
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
              <span className={cx('value')}>
                {model.cpu_allocate ? `${model.cpu_allocate} Cores` : '0 Cores'}
              </span>
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
                {/* <Tooltip
                  contents={
                    <div className={cx('tooltip-wrapper')}>
                      <div>123</div>
                    </div>
                  }
                  iconCustomStyle={{
                    width: '16px',
                    height: '16px',
                  }}
                  contentsCustomStyle={{
                    border: '0.5px solid #DEE9FF',
                    borderRadius: '10px',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                    padding: '20px 24px',
                  }}
                /> */}
              </div>
              <span className={cx('value')}>
                {model.ram_allocate ? `${model.ram_allocate} GB` : '0 GB'}
              </span>
            </div>
          </>
        )}
        {model.instance_name === '-' && (
          <div className={cx('empty-cont')}>
            <p className={cx('txt')}>배포 자원을 설정하시면,</p>
            <p className={cx('txt')}>설정 정보가 화면에 표시됩니다.</p>
          </div>
        )}
        {/* {embedding.instance_name !== '-' && (
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
                  <Badge label='부족' size='sm' type='red' radius='small' />
                  <span className={cx('label')}>vGPU</span>
                </div>
                <span className={cx('value')}>1 EA</span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label='여유'
                    size='sm'
                    type='primary-2'
                    radius='small'
                  />
                  <span className={cx('label')}>vCPU</span>
                </div>
                <span className={cx('value')}>1 Cores</span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge label='부족' size='sm' type='red' radius='small' />
                  <span className={cx('label')}>RAM</span>
                </div>
                <span className={cx('value')}>4 GB</span>
              </div>
            </div>
          </>
        )} */}
        {/* {reranker.instance_name !== '-' && (
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
                  <Badge label='부족' size='sm' type='red' radius='small' />
                  <span className={cx('label')}>vGPU</span>
                </div>
                <span className={cx('value')}>1 EA</span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge
                    label='여유'
                    size='sm'
                    type='primary-2'
                    radius='small'
                  />
                  <span className={cx('label')}>vCPU</span>
                </div>
                <span className={cx('value')}>1 Cores</span>
              </div>
              <div className={cx('between-cont')}>
                <div className={cx('left-cont')}>
                  <Badge label='부족' size='sm' type='red' radius='small' />
                  <span className={cx('label')}>RAM</span>
                </div>
                <span className={cx('value')}>4 GB</span>
              </div>
            </div>
          </>
        )} */}
      </div>
    </PlaygroundFrame>
  );
}
