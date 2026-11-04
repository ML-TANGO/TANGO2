import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';

import { bytesToGB, convertBinaryByte } from '@src/utils';

import AllStorageStack from '../../../AdminStorageContent/AllStorageStack';
import StoragePieChart from '../../../AdminStorageContent/storageComponent/StoragePieChart';
import AdminNodeRateList from '../../nodeComponent/AdminNodeRateList';
import NodeDashboardTemplate from '../../nodeComponent/NodeDashboardTemplate';

const defaultObject = {
  name: '-',
  mem_total: 0,
  mem_alloc: 0,
  mem_used: 0,
  alloc_usage: 0,
  type: '',
};
const defaultArr = [defaultObject, defaultObject];

const RamUsageStatus = ({ isLoading, ram, nodeList }) => {
  const { t } = useTranslation();
  const { total, used, alloc, avail } = ram;

  const { percentage } = calPercent(total, used);
  const labelList = useMemo(() => {
    return [
      {
        label: t('total.label'),
        value: convertBinaryByte(total),
      },
      {
        label: t('allocateGpu.label'),
        value: convertBinaryByte(alloc),
      },
      {
        label: t('storageAvailable.label'),
        value: convertBinaryByte(avail),
      },
      {
        label: t('enable.label'),
        value: convertBinaryByte(used),
      },
    ];
  }, [alloc, avail, t, total, used]);

  return (
    <NodeDashboardTemplate
      pieChartRender={
        <StoragePieChart
          title={t('node.ram.allocate.label')}
          percentage={percentage}
          labelList={labelList}
        />
      }
      listRender={
        <AdminNodeRateList
          title={t('ramUsageRateByNode.label')}
          listData={isLoading ? defaultArr : nodeList}
          columns={[
            {
              label: t('node.label'),
              selector: 'name',
              headStyle: {
                flex: '1 0 280px',
                minWidth: '280px',
                paddingRight: '40px',
              },
              bodyStyle: {
                flex: '1 0 280px',
                minWidth: '280px',
                fontFamily: 'SpoqaB',
                color: '#121619',
                paddingRight: '40px',
              },
            },
            {
              label: t('workspaceStorageTotal.label'),
              selector: 'mem_total',
              headStyle: {
                flex: '0 0 100px',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              bodyStyle: {
                flex: '0 0 100px',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              cell: ({ mem_total }) => {
                return <span>{`${bytesToGB(mem_total)} GB`}</span>;
              },
            },
            {
              label: t('version.label'),
              selector: 'version',
              headStyle: {
                flex: '0 0 100px',
                minWidth: '100px',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              bodyStyle: {
                flex: '0 0 100px',
                minWidth: '100px',
                paddingRight: '30px',
                justifyContent: 'center',
              },
              cell: ({ type }) => {
                return <span>{type ?? '-'}</span>;
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
              cell: ({ mem_total, mem_alloc, mem_used, alloc_usage }) => {
                const { percentage } = calPercent(mem_total, mem_used);
                return (
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <AllStorageStack
                      label='할당'
                      labelValue={convertBinaryByte(mem_alloc)}
                      totalSize={convertBinaryByte(mem_total)}
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
                      labelValue={convertBinaryByte(mem_used)}
                      totalSize={convertBinaryByte(mem_total)}
                      percentage={percentage}
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

export default RamUsageStatus;
