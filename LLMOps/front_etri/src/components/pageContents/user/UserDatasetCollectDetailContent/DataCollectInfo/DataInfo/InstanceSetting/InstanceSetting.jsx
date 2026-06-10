import React from 'react';

import { Badge } from '@jonathan/ui-react';

import PlaygroundFrame from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './InstanceSetting.module.scss';

const cx = classNames.bind(style);

export default function InstanceSetting({
  instance_name,
  instance_count,
  instance_usage_info,
}) {
  const { cpu, memory } = instance_usage_info;

  const isAvailable = cpu.available && memory.available;

  return (
    <PlaygroundFrame style={{ minHeight: 'fit-content' }}>
      <div className={cx('flex-32')}>
        <div className={cx('title-cont')}>
          <h3>인스턴스 설정 정보</h3>
          <span className={cx(isAvailable && 'available')}>
            {isAvailable ? '즉시 사용 가능' : '대기 필요'}
          </span>
        </div>
        <div className={cx('flex-16')}>
          <div className={cx('between-cont')}>
            <div className={cx('left-cont')}>
              <span className={cx('label')}>인스턴스</span>
              <span className={cx('value')}>{instance_name}</span>
            </div>
            <span className={cx('value')}>{instance_count} EA</span>
          </div>
          <div className={cx('border')}></div>
          <div className={cx('between-cont')}>
            <div className={cx('left-cont')}>
              <Badge
                label={cpu.available ? '여유' : '부족'}
                size='sm'
                radius='small'
                type={cpu.available ? 'primary-2' : 'red'}
              />
              <span className={cx('label')}>vCPU</span>
            </div>
            <span className={cx('value')}>{cpu.available_cpu_core} Cores</span>
          </div>
          <div className={cx('between-cont')}>
            <div className={cx('left-cont')}>
              <Badge
                label={memory.available ? '여유' : '부족'}
                size='sm'
                radius='small'
                type={memory.available ? 'primary-2' : 'red'}
              />
              <span className={cx('label')}>RAM</span>
            </div>
            <span className={cx('value')}>{memory.available_memory} GB</span>
          </div>
        </div>
      </div>
    </PlaygroundFrame>
  );
}
