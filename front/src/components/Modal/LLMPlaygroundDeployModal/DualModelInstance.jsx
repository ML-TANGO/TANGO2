import React, { useMemo } from 'react';

import { Checkbox, InputNumber } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import InstanceAllocate from './InstanceAllocate';

import classNames from 'classnames/bind';
import style from './LLMPlaygroundDeployModal.module.scss';

const cx = classNames.bind(style);

const getCapacity = (instance) =>
  (instance?.instance_allocate ?? 0) * (instance?.gpu_allocate ?? 0);

export default function DualModelInstance({
  isFetching,
  instanceList,
  selectedInstanceId,
  promptGpuCount,
  inferenceGpuCount,
  onSelectInstance,
  onPromptGpuChange,
  onInferenceGpuChange,
}) {
  const selectedInstance = useMemo(
    () =>
      instanceList.find(
        (instance) =>
          String(instance.instance_id) === String(selectedInstanceId),
      ),
    [instanceList, selectedInstanceId],
  );
  const capacity = getCapacity(selectedInstance);
  const requestedGpu =
    Number(promptGpuCount || 0) + Number(inferenceGpuCount || 0);

  const columns = [
    {
      label: '인스턴스',
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
      cell: (instance) => {
        const checked =
          String(instance.instance_id) === String(selectedInstanceId);
        return (
          <Checkbox
            label={
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span style={{ color: checked && '#2D76F8' }}>
                  {instance.instance_name}
                  {/* GPU 총량 0은 선택 불가가 아니라 CPU 배포 계약이므로 용도를 명시한다. */}
                  {getCapacity(instance) === 0 && ' (CPU 전용)'}
                </span>
                <InstanceTooltip
                  instanceType={instance.instance_type}
                  gpuName={instance.resource_name}
                  gpuAllocateNum={instance.gpu_allocate}
                  cpuAllocateNum={instance.cpu_allocate}
                  ramAllocateNum={instance.ram_allocate}
                />
              </div>
            }
            checked={checked}
            onChange={(event) =>
              onSelectInstance(
                event.target.checked ? instance.instance_id : null,
              )
            }
          />
        );
      },
    },
    {
      label: '인스턴스 수',
      headStyle: {
        flex: '1 90px',
        minWidth: '90px',
        paddingRight: '32px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 90px',
        minWidth: '90px',
        paddingRight: '32px',
      },
      cell: ({ instance_allocate }) => `${instance_allocate ?? 0} EA`,
    },
    {
      label: '총 GPU',
      headStyle: {
        flex: '1 90px',
        minWidth: '90px',
        textAlign: 'center',
      },
      bodyStyle: {
        flex: '1 90px',
        minWidth: '90px',
      },
      cell: (instance) => `${getCapacity(instance)} EA`,
    },
  ];

  return (
    <>
      <InputBoxWithLabel
        labelText='모델 인스턴스 선택'
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
        labelText='LLM1 GPU 할당'
        labelSize='large'
        labelStyle={{ marginBottom: '16px' }}
        optionalText={selectedInstance?.resource_name}
        disableErrorMsg
      >
        <InputNumber
          min={0}
          max={capacity}
          step={1}
          value={promptGpuCount}
          onChange={({ value }) => onPromptGpuChange(value)}
          placeholder={
            selectedInstance
              ? `사용 가능: ${capacity}`
              : '상단의 인스턴스를 선택해주세요.'
          }
          isReadOnly={!selectedInstance}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='LLM2 GPU 할당'
        labelSize='large'
        labelStyle={{ marginBottom: '16px' }}
        optionalText={selectedInstance?.resource_name}
        disableErrorMsg
      >
        <InputNumber
          min={0}
          max={capacity}
          step={1}
          value={inferenceGpuCount}
          onChange={({ value }) => onInferenceGpuChange(value)}
          placeholder={
            selectedInstance
              ? `사용 가능: ${capacity}`
              : '상단의 인스턴스를 선택해주세요.'
          }
          isReadOnly={!selectedInstance}
        />
      </InputBoxWithLabel>
      <div className={cx('border')} />
      <p
        className={cx(
          'model-instance-message',
          requestedGpu <= capacity ? 'blue' : 'red',
        )}
      >
        LLM1 + LLM2 GPU {requestedGpu} / 사용 가능 {capacity}
      </p>
    </>
  );
}
