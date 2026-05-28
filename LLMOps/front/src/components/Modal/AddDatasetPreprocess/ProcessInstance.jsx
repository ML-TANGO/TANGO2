import React from 'react';
import { useTranslation } from 'react-i18next';

import { Checkbox, InputNumber } from '@jonathan/ui-react';

// import ProcessToolTip from './ProcessToolTip';
import Tooltip from '@src/components/atoms/Tooltip';

import classNames from 'classnames/bind';
import style from './ProcessInstance.module.scss';

const cx = classNames.bind(style);

const ProcessInstance = ({
  id,
  instanceName,
  resourceName,
  max,
  checked,
  used,
  handleInstanceCheck,
  handleInstanceUsed,
  cpu,
  gpu,
  ram,
}) => {
  const { t } = useTranslation();

  return (
    <div className={cx('container')}>
      <div className={cx('instance')}>
        <Checkbox
          value={id}
          disabled={`${max}` === 0}
          customLabelStyle={{
            padding: '0 0 0 3px',
            fontSize: '14px',
          }}
          name='gpuModel'
          checked={checked}
          onChange={() => {
            handleInstanceCheck({ id });
          }}
        />
        <span>{instanceName}</span>
        <Tooltip
          iconCustomStyle={{
            width: '16px',
            height: '16px',
            marginLeft: '8px',
          }}
          contentsCustomStyle={{
            width: '180px',
            minWidth: '180px',
            maxWidth: '180px',
            height: '100px',
            transform: 'translate(30px, -30px)',
          }}
          contents={
            <div className={cx('tool-tip')}>
              <div className={cx('resource-name')}>
                {resourceName ? resourceName : instanceName}
              </div>
              <div className={cx('info')}>
                <span>vGPU</span>
                <span>{gpu} EA</span>
              </div>
              <div className={cx('info')}>
                <span>vCPU</span>
                <span>{cpu} Cores</span>
              </div>
              <div className={cx('info')}>
                <span>RAM</span>
                <span>{ram} GB</span>
              </div>
            </div>
          }
        />
      </div>
      <div className={cx('total')}>{max} EA</div>
      <div className={cx('allocate')}>
        <InputNumber
          name='workspaceInput'
          placeholder={`${t('currentAvailableCount')} : ${
            max === '' ? '0' : max
          }`}
          min={0}
          max={max}
          value={used}
          onChange={(e) => {
            if (`${max}` === '0') return;
            let inputValue = e.value;

            if (e.value > max) {
              inputValue = max;
            }
            handleInstanceUsed({ id, value: inputValue });
          }}
          isReadOnly={`${max}` === '0'}
          disabled={`${max}` === '0'}
          customSize={{ width: '100%' }}
        />
      </div>
    </div>
  );
};

export default ProcessInstance;
