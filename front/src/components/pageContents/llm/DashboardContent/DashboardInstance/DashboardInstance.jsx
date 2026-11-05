import React from 'react';
import { useTranslation } from 'react-i18next';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';
import ListStack from '@src/components/molecules/ListStack';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardInstance.module.scss';

const cx = classNames.bind(style);

const Item = ({
  instanceName,
  totalValue,
  gpu_resource_group_name,
  cpu_allocate,
  gpu_allocate,
  ram_allocate,
  remaining_rate,
  instance_type,
  used_rate,
}) => {
  const { t } = useTranslation();
  const percent = 100 - remaining_rate.remaining_rate;

  const stackListValue = used_rate.map((info) => {
    const { cpu, gpu, ram } = info.used_resource;

    return {
      ...info,
      width: info.used_rate,
      value: info.used_rate,
      tooltipContent: (
        <DarkTooltip
          direction='bottom'
          content={
            <div
              style={{
                display: 'flex',
                gap: '8px',
                fontFamily: 'SpoqaB',
                fontSize: '10px',
              }}
              className={cx('tooltip-cont')}
            >
              <div className={cx('name-cont')}>
                <span>{t('Model')}</span>
                <span>{info.item_name}</span>
                <span>{Math.floor(info.used_rate)} %</span>
              </div>
              <div className={cx('border')}></div>
              <div className={cx('wks-bar-box')}>
                <div className={cx('bar-label')}>vGPU</div>
                <div>{gpu ?? 0} EA</div>
              </div>
              <div className={cx('wks-bar-box')}>
                <div className={cx('bar-label')}>vCPU</div>
                <div>{cpu ?? 0} Cores</div>
              </div>

              <div className={cx('wks-bar-box')}>
                <div className={cx('bar-label')}>RAM</div>
                <div>{ram.toFixed(2) ?? 0} GB</div>
              </div>
            </div>
          }
        />
      ),
    };
  });

  const { remaining_resource } = remaining_rate;
  const { cpu: remainCpu, gpu: remainGpu, ram: remainRam } = remaining_resource;
  const totalStackList = [
    ...stackListValue,
    {
      width: remaining_rate.remaining_rate,
      value: remaining_rate.remaining_rate,
      color: '#fff',
      tooltipContent: (
        <DarkTooltip
          direction='bottom'
          content={
            <div
              style={{
                display: 'flex',
                gap: '8px',
                fontFamily: 'SpoqaB',
                fontSize: '10px',
              }}
              className={cx('tooltip-cont')}
            >
              <div className={cx('name-cont')}>
                <span>잔여량</span>
                <span>{Math.floor(remaining_rate.remaining_rate)} %</span>
              </div>
              <div className={cx('border')}></div>
              <div className={cx('wks-bar-box')}>
                <div className={cx('bar-label')}>vGPU</div>
                <div>{remainGpu ?? 0} EA</div>
              </div>
              <div className={cx('wks-bar-box')}>
                <div className={cx('bar-label')}>vCPU</div>
                <div>{remainCpu ?? 0} Cores</div>
              </div>

              <div className={cx('wks-bar-box')}>
                <div className={cx('bar-label')}>RAM</div>
                <div>{remainRam ?? 0} GB</div>
              </div>
            </div>
          }
        />
      ),
    },
  ];

  return (
    <div className={cx('tr')}>
      <div className={cx('td')}>
        <span className={cx('instanceName-txt')}>{instanceName}</span>
        <div className={cx('tooltip')}>
          <InstanceTooltip
            title={instanceName}
            gpuName={gpu_resource_group_name}
            gpuAllocateNum={gpu_allocate}
            cpuAllocateNum={cpu_allocate}
            ramAllocateNum={ram_allocate}
            instanceType={instance_type}
          />
        </div>
      </div>
      <div className={cx('td')}>
        <div className={cx('instance-usage-cont')}>
          <div className={cx('upper')}>
            <span>{t('total.label')}</span>
            <span>{totalValue} EA</span>
          </div>
          <div className={cx('under')}>
            <ListStack
              isTooltip={true}
              tooltipDirection={'bottom'}
              stackList={totalStackList}
              totalValue={100}
            />
            <span className={cx('percent')}>{Math.floor(percent)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const DashboardInstanceList = ({ instances_used }) => {
  const { t } = useTranslation();
  if (instances_used === null)
    return (
      <div className={cx('error')}>
        <span>{t('noResponse.message')}</span>
      </div>
    );
  if (instances_used.length === 0)
    return (
      <div className={cx('error')}>
        <span>{t('noData.instance.message')}</span>
      </div>
    );

  return (
    <div className={cx('tbody')}>
      {instances_used.map((info, idx) => {
        const {
          instance_name,
          instance_allocate,
          remaining_rate,
          used_rate,
          gpu_resource_group_name,
          gpu_allocate,
          cpu_allocate,
          ram_allocate,
          instance_type,
        } = info;

        return (
          <Item
            key={idx}
            instanceName={instance_name}
            totalValue={instance_allocate}
            gpu_resource_group_name={gpu_resource_group_name}
            remaining_rate={remaining_rate}
            gpu_allocate={gpu_allocate}
            cpu_allocate={cpu_allocate}
            ram_allocate={ram_allocate}
            instance_type={instance_type}
            used_rate={used_rate}
          />
        );
      })}
    </div>
  );
};

export default function DashboardInstance({ title, instances_used }) {
  const { t } = useTranslation();
  return (
    <div className={cx('dashboard-frame-cont')}>
      <div className={cx('title-cont')}>
        <div className={cx('upper')}>
          <span className={cx('title-txt')}>{title}</span>
          <div className={cx('platform-cont')}>
            <div className={cx('dot')} />
            <span className={cx('platform-txt')}>GenAI Platform</span>
          </div>
        </div>
        <div className={cx('under')}>{t('llm.dashboard.instance.message')}</div>
      </div>
      <div className={cx('thead')}>
        <div className={cx('tr')}>
          <div className={cx('td')}>{t('instanceName.label')}</div>
          <div className={cx('td')}>{t('instanceUsage.label')}</div>
        </div>
      </div>
      <DashboardInstanceList instances_used={instances_used} />
    </div>
  );
}
