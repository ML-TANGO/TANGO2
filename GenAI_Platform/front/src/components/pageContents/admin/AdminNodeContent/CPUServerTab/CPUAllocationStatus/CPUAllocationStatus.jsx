import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';

import AllStorageStack from '../../../AdminStorageContent/AllStorageStack';
import StoragePieChart from '../../../AdminStorageContent/storageComponent/StoragePieChart';
import AdminNodeRateList from '../../nodeComponent/AdminNodeRateList';
import NodeDashboardTemplate from '../../nodeComponent/NodeDashboardTemplate';

const defaultObject = {
  name: '-',
  npu_count: 0,
  hostList: [''],
  cpu_core: 0,
  cpu_alloc: 0,
  cpu_used: 0,
  alloc_usage: 0,
  used_usage: 0,
};
const defaultArr = [defaultObject, defaultObject];

const CPUAllocationStatus = ({ isLoading, cpu, nodeList }) => {
  const { t } = useTranslation();
  const { total, used, alloc, avail } = cpu;
  const { percentage } = calPercent(total, used);

  const labelList = useMemo(() => {
    return [
      {
        label: t('total.label'),
        value: `${total} Cores`,
      },
      {
        label: t('allocateGpu.label'),
        value: `${alloc} Cores`,
      },
      {
        label: t('storageAvailable.label'),
        value: `${avail} Cores`,
      },
      {
        label: t('enable.label'),
        value: `${used} Cores`,
      },
    ];
  }, [alloc, avail, t, total, used]);

  return (
    <NodeDashboardTemplate
      pieChartRender={
        <StoragePieChart
          title={t('node.cpu.allocate.label')}
          percentage={percentage}
          labelList={labelList}
        />
      }
      listRender={
        <AdminNodeRateList
          title={t('coreAllocationRateByCpuModel.label')}
          listData={isLoading ? defaultArr : nodeList}
          columns={[
            {
              label: t('cpuModel.label'),
              selector: 'name',
              headStyle: {
                flex: '1 303px',
                minWidth: '303px',
                paddingRight: '40px',
              },
              bodyStyle: {
                flex: '1 303px',
                minWidth: '303px',
                paddingRight: '40px',
                fontSize: '12px',
                fontFamily: 'SpoqaM',
              },
              cell: ({ name, hostList }) => {
                if (!name) return '-';
                return (
                  <div>
                    <p
                      style={{
                        fontFamily: 'SpoqaB',
                        fontSize: '14px',
                        color: '#121619',
                        margin: 'initial',
                        marginBottom: '8px',
                      }}
                    >
                      {name ?? '-'}
                    </p>
                    <div>
                      {hostList.map((hostName, idx) => {
                        return (
                          <span
                            key={idx}
                            style={{
                              fontFamily: 'SpoqaM',
                              fontSize: '14px',
                              lineHeight: '22px',
                              color: '#747474',
                            }}
                          >
                            {hostName}
                            {hostList.length !== idx + 1 && ','}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              },
            },
            {
              label: t('node.clockFrequency.label'),
              selector: 'clockFrequency',
              headStyle: {
                flex: '1 70px',
                minWidth: '70px',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              bodyStyle: {
                flex: '1 70px',
                minWidth: '70px',
                paddingRight: '30px',
                fontSize: '14px',
                fontFamily: 'SpoqaM',
                color: '#121619',
                justifyContent: 'center',
              },
              cell: ({ name }) => {
                const frequency = name.split('@')[1];
                return <span>{frequency ?? '-'}</span>;
              },
            },
            {
              label: t('all.cores.count'),
              selector: 'name',
              headStyle: {
                flex: '1 100px',
                minWidth: '100px',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              bodyStyle: {
                flex: '1 100px',
                minWidth: '100px',
                fontSize: '14px',
                fontFamily: 'SpoqaM',
                color: '#121619',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              cell: ({ cpu_core }) => {
                return <span>{`${cpu_core} Cores`}</span>;
              },
            },
            {
              label: t('allocate.usage.label'),
              headStyle: {
                flex: '1 422px',
                minWidth: '422px',
                justifyContent: 'center',
              },
              bodyStyle: {
                flex: '1 422px',
                minWidth: '422px',
                justifyContent: 'center',
              },
              cell: ({
                cpu_core,
                cpu_alloc,
                cpu_used,
                alloc_usage,
                used_usage,
              }) => {
                return (
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <AllStorageStack
                      label='할당'
                      labelValue={`${cpu_alloc} Cores`}
                      totalSize={`${cpu_core} Cores`}
                      percentage={alloc_usage.toFixed(0)}
                    />
                    <div
                      style={{
                        width: '100%',
                        height: '1px',
                        backgroundColor: '#DBDBDB',
                        margin: '16px 0',
                      }}
                    />
                    <AllStorageStack
                      label='사용'
                      labelValue={`${cpu_used} Cores`}
                      totalSize={`${cpu_core} Cores`}
                      percentage={used_usage.toFixed(0)}
                    />
                  </div>
                );
              },
            },
          ]}
        />
      }
    />
  );
};

export default CPUAllocationStatus;
