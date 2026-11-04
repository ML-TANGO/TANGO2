import { useTranslation } from 'react-i18next';

import { Checkbox, InputNumber } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import InstanceAllocate from '../../LLMPlaygroundDeployModal/InstanceAllocate';

import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

export default function CollectResourceSetting({
  isFetching,
  listData,
  handleSelectInstance,
  handleGpuValue,
}) {
  const { t } = useTranslation();

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
          instance_id,
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
                <span>{instance_name}</span>
                <InstanceTooltip
                  instanceType={instance_type}
                  gpuName={resource_name}
                  gpuAllocateNum={listData[idx].gpu_allocate}
                  cpuAllocateNum={cpu_allocate}
                  ramAllocateNum={ram_allocate}
                />
              </div>
            }
            checked={front.isCheck}
            onChange={(e) => {
              handleSelectInstance(e.target.checked, instance_id);
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
      cell: ({ instance_allocate, instance_id, front }) => {
        return (
          <InputNumber
            min={0}
            max={instance_allocate}
            step={1}
            value={front.value}
            onChange={({ value }) => {
              handleGpuValue(value, instance_id);
            }}
            placeholder={`사용가능: ${instance_allocate}`}
            isReadOnly={instance_allocate === 0}
          />
        );
      },
    },
  ];

  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={t('collect.resource.setting')}
        optionalText={t('selectInstance.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
      >
        <InstanceAllocate
          isFetching={isFetching}
          listData={listData}
          columns={columns}
        />
      </InputBoxWithLabel>
    </div>
  );
}
