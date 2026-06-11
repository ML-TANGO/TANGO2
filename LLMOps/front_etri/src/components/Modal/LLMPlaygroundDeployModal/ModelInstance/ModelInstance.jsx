import React from 'react';
import { useTranslation } from 'react-i18next';

import { Checkbox, InputNumber } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import InstanceAllocate from '../InstanceAllocate';

import { calFindSelectedReturnValue } from '../util';

import classNames from 'classnames/bind';
import style from '../LLMPlaygroundDeployModal.module.scss';

const cx = classNames.bind(style);

export default function ModelInstance({
  isFetching,
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
  const { gpu_allocate, front } = findSelectedValue;

  const columns = [
    {
      label: t('modelName.label'),
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
                <span style={{ color: front.isCheck && '#2D76F8' }}>
                  {instance_name}
                </span>
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
      <InputBoxWithLabel
        labelText={t('playground.model.select.label')}
        labelSize='large'
        labelStyle={{ marginBottom: '16px' }}
        disableErrorMsg
      >
        <InstanceAllocate
          listData={instanceList}
          columns={columns}
          isFetching={isFetching}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText={t('playground.gpu.allocate')}
        labelSize='large'
        labelStyle={{ marginBottom: '16px' }}
        optionalText={resource_name}
        disableErrorMsg
      >
        <InputNumber
          min={0}
          max={gpu_allocate * front.value}
          step={1}
          value={gpuValue}
          onChange={({ value }) =>
            handleModelValue(value, instanceType, instance_id)
          }
          placeholder={
            resource_name
              ? `사용 가능: ${gpu_allocate * front.value}`
              : '상단의 인스턴스를 선택해주세요.'
          }
        />
      </InputBoxWithLabel>
      <div className={cx('border')} />
      <p className={cx('model-instance-message', 'blue')}>
        {t('playground.model.instance.warn.message1')}
      </p>
    </>
  );
}
