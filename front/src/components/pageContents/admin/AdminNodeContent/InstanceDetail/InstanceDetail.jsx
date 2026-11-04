import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';
import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';
import ListStack from '@src/components/molecules/ListStack';

import NodeRateList from '../nodeComponent/AdminNodeRateList';
import Stack from '../nodeComponent/NodeRateList/Stack';
import GraphCont from './GraphCont';

import classNames from 'classnames/bind';
import style from './InstanceDetail.module.scss';

const cx = classNames.bind(style);

export const calAllocateInstanceValue = (allocateWorkspaceList) => {
  if (!allocateWorkspaceList) return 0;
  const copyAllocateList = allocateWorkspaceList.slice();
  const allocatetotalValue = copyAllocateList.reduce((acc, cur) => {
    acc += cur.instance_count;
    return acc;
  }, 0);
  return allocatetotalValue;
};

const calInstanceName = (info) => {
  const { cpu_count, gpu_count, gpu_name, ram_count } = info;
  if (gpu_name === 'No Resource Group') return `CPU.${cpu_count}.${ram_count}`;
  return `${gpu_name}.${gpu_count}.${cpu_count}.${ram_count}`;
};

const handleRowClick = (idx, instanceList, setAllocateWorkspaceList) => {
  const findInstanceObject = instanceList[idx];
  const instanceTotalValue = findInstanceObject.instance_total_count;

  const allocateWorkspaceList = findInstanceObject.allocate_workspace_list;
  const inGpuNameList = allocateWorkspaceList.map((el) => {
    const percent = ((el.instance_count / instanceTotalValue) * 100).toFixed(0);
    return {
      ...el,
      ...findInstanceObject,
      gpuName:
        findInstanceObject.gpu_name === 'No Resource Group'
          ? calInstanceName(findInstanceObject)
          : findInstanceObject.gpu_name,
      percent,
    };
  });
  setAllocateWorkspaceList(inGpuNameList);
};

const defaultObject = {
  cpu_count: 0,
  gpu_count: 0,
  gpu_name: '',
  ram_count: 0,
  allocate_workspace_list: [],
  instance_total_count: 0,
};
const defaultArr = [defaultObject, defaultObject, defaultObject];

const InstanceDetail = ({ isLoading, instanceList }) => {
  const { t } = useTranslation();

  const [allocateWorkspaceList, setAllocateWorkspaceList] = useState([]);
  const instanceTotalValue = instanceList.reduce((acc, cur) => {
    acc += cur.instance_total_count;
    return acc;
  }, 0);

  const columns = [
    {
      label: t('instanceName.label'),
      headStyle: {
        flex: '1 261px',
        minWidth: '261px',
        paddingRight: '30px',
      },
      bodyStyle: {
        flex: '1 261px',
        minWidth: '261px',
        paddingRight: '30px',
      },
      cell: (info) => {
        const instanceName = calInstanceName(info);
        return (
          <div className={cx('flex-column')} style={{ gap: '8px' }}>
            <span className={cx('instance-txt')}>{instanceName}</span>
            <div className={cx('flex-row')}>
              <span className={cx('instance-label')}>vGpu</span>
              <span className={cx('instance-value')}>
                {info.gpu_name === 'No Resource Group' ? '-' : info.gpu_name}
              </span>
            </div>
            <div className={cx('flex-row')}>
              <span className={cx('instance-label')}>vCpu</span>
              <span className={cx('instance-value')}>
                {info.cpu_count} Cores
              </span>
            </div>
            <div className={cx('flex-row')}>
              <span className={cx('instance-label')}>RAM</span>
              <span className={cx('instance-value')}>{info.ram_count} GB</span>
            </div>
          </div>
        );
      },
    },
    {
      label: t('allocate.workspace.label'),
      headStyle: {
        flex: '1 108px',
        minWidth: '108px',
        paddingRight: '36px',
        justifyContent: 'center',
      },
      bodyStyle: {
        flex: '1 108px',
        minWidth: '108px',
        paddingRight: '36px',
        justifyContent: 'center',
      },
      cell: ({ allocate_workspace_list }) => {
        const allocateWorkspaceLength = allocate_workspace_list.length;
        return <span>{allocateWorkspaceLength}</span>;
      },
    },
    {
      label: t('node.instance.allocate.label'),
      headStyle: {
        flex: '1 240px',
        minWidth: '240px',
        paddingRight: '36px',
      },
      bodyStyle: {
        flex: '1 240px',
        minWidth: '240px',
        paddingRight: '36px',
      },
      cell: (info) => {
        const allocatetotalValue = calAllocateInstanceValue(
          info.allocate_workspace_list,
        );
        const transfromAllocateValue = info.allocate_workspace_list.map(
          (el) => {
            return {
              ...el,
              value: el.instance_count,
              tooltipContent: (
                <DarkTooltip
                  direction='top'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                    >
                      <span>{el.workspace_name}</span>
                      <span>{el.instance_count}EA</span>
                    </div>
                  }
                />
              ),
            };
          },
        );
        const { percentage } = calPercent(
          info.instance_total_count,
          allocatetotalValue,
        );
        return (
          <div className={cx('flex-column')}>
            <div
              className={cx('flex-row')}
              style={{
                justifyContent: 'space-between',
                marginBottom: '8px',
              }}
            >
              <div className={cx('left-cont')}>
                <span className={cx('label')}>{t('allocateGpu.label')}</span>
                <span className={cx('value')}>
                  {info.instance_total_count} EA
                </span>
              </div>
              <div className={cx('right-cont')}>{percentage} %</div>
            </div>
            <div className={cx('flex-cont')} style={{ marginBottom: '8px' }}>
              <ListStack
                isTooltip={true}
                tooltipDirection='top'
                stackList={transfromAllocateValue}
                totalValue={info.instance_total_count}
              />
            </div>
            <div className={cx('flex-cont')}>
              <div className={cx('unit-cont')}>
                <span>(</span>
                <span style={{ width: '34px' }}>{allocatetotalValue}</span>
                <span>EA</span>
                <span>/</span>
                <span style={{ width: '34px' }}>
                  {info.instance_total_count}
                </span>
                <span>EA</span>
                <span>)</span>
              </div>
            </div>
          </div>
        );
      },
    },
  ];

  const usageColumn = [
    {
      label: t('workspace.usage.label'),
      headStyle: {
        flex: '1 108px',
        minWidth: '108px',
        paddingRight: '36px',
        justifyContent: 'center',
      },
      bodyStyle: {
        flex: '1 108px',
        minWidth: '108px',
        paddingRight: '36px',
        justifyContent: 'center',
      },
      cell: ({ workspace_name, gpuName, percent, ...rest }) => {
        const { cpu_count, gpu_count, ram_count } = rest;
        return (
          <div className={cx('flex-column')}>
            <span className={cx('workspace-name-txt')}>{gpuName}</span>
            <div
              className={cx('flex-row', 'space-between')}
              style={{ marginBottom: '8px' }}
            >
              <div className={cx('left-cont')}>{workspace_name}</div>
              <div className={cx('right-cont')}>{percent} %</div>
            </div>
            <div className={cx('stack-cont')}>
              <Stack
                rate={percent}
                isRateLabel={false}
                isTooltip={true}
                tooltipContent={
                  <DarkTooltip
                    direction='bottom'
                    content={
                      <div className={cx('tooltip-cont')}>
                        <span className={cx('workspace-name-txt')}>
                          {workspace_name}
                        </span>
                        <div className={cx('tooltip-row')}>
                          <span>vGPU</span>
                          <span>{gpu_count}</span>
                          <span>EA</span>
                        </div>
                        <div className={cx('tooltip-row')}>
                          <span>vCPU</span>
                          <span>{cpu_count}</span>
                          <span>Cores</span>
                        </div>
                        <div className={cx('tooltip-row')}>
                          <span>RAM</span>
                          <span>{ram_count}</span>
                          <span>GB</span>
                        </div>
                      </div>
                    }
                  />
                }
              />
            </div>
          </div>
        );
      },
    },
  ];

  return (
    <div className={cx('instance-cont')}>
      <GraphCont
        instanceList={instanceList}
        instanceTotalValue={instanceTotalValue}
      />
      <div className={cx('instance-content-cont')}>
        <NodeRateList
          columns={columns}
          listData={isLoading ? defaultArr : instanceList}
          handleRowClick={(idx) => {
            handleRowClick(idx, instanceList, setAllocateWorkspaceList);
          }}
          style={{ height: '408px' }}
        />
        <NodeRateList
          columns={usageColumn}
          listData={allocateWorkspaceList}
          style={{ height: '408px' }}
        />
      </div>
    </div>
  );
};

export default InstanceDetail;
