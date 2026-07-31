import { Checkbox, InputNumber } from '@tango/ui-react';

import React from 'react';
import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import { calFindSelectedReturnValue } from '../util';

import InstanceAllocate from '../InstanceAllocate';

// CSS Module
import classNames from 'classnames/bind';
import style from '../RagTestModal.module.scss';

const cx = classNames.bind(style);

export default function RagrerankerModelInstance({
  instanceType,
  instanceList,
  selectedModelValue,
  gpuValue,
  handleCheckbox,
  handleInstanceValue,
  handleModelValue,
}) {
  const { t } = useTranslation();

  const { instance_id, resource_name, front, gpu_allocate } =
    selectedModelValue;

  const { value: selectedAlloc } = front || { value: 0 };

  const columns = [
    {
      label: t('instanceName.label'),
      selector: 'instance_name',
      headStyle: {
        flex: '1 289px',
        paddingLeft: '28px',
        paddingRight: '48px',
      },
      bodyStyle: {
        flex: '1 289px',
        paddingRight: '48px',
      },
      cell: (
        {
          instance_name,
          resource_name,
          instance_type,
          cpu_allocate,
          gpu_allocate,
          ram_allocate,
          instance_allocate,
          front,
        },
        idx,
      ) => {
        return (
          <Checkbox
            label={
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span>{instance_name}</span>
                <InstanceTooltip
                  instanceType={instance_type}
                  gpuName={resource_name}
                  gpuAllocateNum={instanceList[idx].tooltipGpuAllocate}
                  cpuAllocateNum={cpu_allocate}
                  ramAllocateNum={ram_allocate}
                />
              </div>
            }
            checked={front.isCheck}
            onChange={(e) => {
              handleCheckbox(instanceType, e.target.checked, idx);
            }}
            disabled={instance_allocate === 0}
          />
        );
      },
    },
    {
      label: t('totalAmount.label'),
      headStyle: {
        flex: '1 60px',
        minWidth: '60px',
        paddingRight: '48px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 60px',
        minWidth: '60px',
        paddingRight: '48px',
      },
      cell: ({ instance_allocate }) => {
        return `${instance_allocate} EA`;
      },
    },
    {
      label: t('allocation.label'),
      headStyle: {
        flex: '1 120px',
        minWidth: '120px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 120px',
        minWidth: '120px',
      },
      cell: ({ instance_allocate, front }, idx) => {
        return (
          <InputNumber
            min={0}
            max={instance_allocate}
            step={1}
            value={front.value}
            onChange={({ value }) => {
              handleInstanceValue(instanceType, value, idx);
            }}
            placeholder={`사용가능: ${instance_allocate}`}
            isReadOnly={instance_allocate === 0}
          />
        );
      },
    },
  ];

  return (
    <>
      <div className={cx('border')} />
      <div className={cx('label')}>{t('ragRerankerModel.label')}</div>
      <InputBoxWithLabel
        labelText={t('instanceAllocation.label')}
        labelSize='large'
        labelStyle={{ marginBottom: '16px' }}
        disableErrorMsg
      >
        <InstanceAllocate listData={instanceList} columns={columns} />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText={t('gpuAllocation.label')}
        labelSize='large'
        labelStyle={{ marginBottom: '16px' }}
        optionalText={resource_name}
        disableErrorMsg
      >
        <InputNumber
          min={0}
          max={gpu_allocate * selectedAlloc}
          step={1}
          value={gpuValue}
          onChange={({ value }) =>
            handleModelValue(value, instanceType, instance_id)
          }
          placeholder={
            resource_name
              ? `사용 가능: ${gpu_allocate * selectedAlloc}`
              : '상단의 인스턴스를 선택해주세요.'
          }
        />
      </InputBoxWithLabel>
      {/* <div className={cx('message-cont')}>
        <p className={cx('model-instance-message', 'red')}>
          {t('playground.model.instance.warn.message2')}
        </p>
        <p className={cx('model-instance-message', 'red')}>
          {t('playground.model.instance.warn.message3')}
        </p>
      </div> */}
    </>
  );
}
