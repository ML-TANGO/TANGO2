import { Checkbox, InputNumber } from '@jonathan/ui-react';

import React from 'react';
import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import { calFindSelectedReturnValue } from '../util';

import InstanceAllocate from '../InstanceAllocate';

import classNames from 'classnames/bind';
import style from '../RagTestModal.module.scss';

const cx = classNames.bind(style);

export default function RagInbedingModelInstance({
  instanceType,
  instanceList,
  selectedModelValue,
  gpuValue,
  handleCheckbox,
  handleInstanceValue,
  handleModelValue,
}) {
  const { t } = useTranslation();

  const { instance_id, resource_name } = selectedModelValue;

  const findSelectedValue = calFindSelectedReturnValue(
    instanceList,
    instance_id,
  );
  const { gpu_allocate, tooltipGpuAllocate } = findSelectedValue;

  const { front } = selectedModelValue;
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
                  cpuAllocateNum={cpu_allocate}
                  ramAllocateNum={ram_allocate}
                  gpuAllocateNum={instanceList[idx].tooltipGpuAllocate}
                />
              </div>
            }
            checked={front.isCheck}
            onChange={(e) => {
              handleCheckbox(instanceType, e.target.checked, idx);
            }}
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
          />
        );
      },
    },
  ];
  return (
    <>
      <div className={cx('label')}>{t('ragEmbeddedModel.label')}</div>
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
          placeholder={`사용 가능: ${gpu_allocate * selectedAlloc}`}
        />
      </InputBoxWithLabel>
    </>
  );
}
