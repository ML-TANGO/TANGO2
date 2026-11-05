import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';

import AllStorageStack from '../../../AdminStorageContent/AllStorageStack';
import StoragePieChart from '../../../AdminStorageContent/storageComponent/StoragePieChart';
import AdminNodeRateList from '../../nodeComponent/AdminNodeRateList';
import NodeDashboardTemplate from '../../nodeComponent/NodeDashboardTemplate';

const getColumns = (target, t) => {
  if (target === 'model') {
    return [
      {
        label: t('gpuModel.label'),
        selector: 'name',
        headStyle: { flex: '1 180px', minWidth: '180px', paddingRight: '30px' },
        bodyStyle: {
          flex: '1 180px',
          minWidth: '180px',
          paddingRight: '30px',
          color: '#121619',
          fontFamily: 'SpoqaB',
          fontSize: '14px',
          lineHeight: '14px',
        },
        cell: ({ name }) => <span>{name ?? '-'}</span>,
      },
      {
        label: t('all.count.label'),
        selector: 'total',
        headStyle: {
          flex: '1 80px',
          minWidth: '80px',
          justifyContent: 'center',
          paddingRight: '30px',
        },
        bodyStyle: {
          flex: '1 80px',
          minWidth: '80px',
          justifyContent: 'center',
          fontSize: '14px',
          fontFamily: 'SpoqaM',
          color: '#121619',
          paddingRight: '30px',
        },
        cell: ({ total }) => <span>{`${total ?? '0'} EA`}</span>,
      },
      {
        label: 'CUDA Cores',
        selector: 'cudaValues',
        headStyle: {
          flex: '1 100px',
          minWidth: '100px',
          justifyContent: 'center',
          paddingRight: '30px',
        },
        bodyStyle: {
          flex: '1 100px',
          minWidth: '100px',
          justifyContent: 'center',
          paddingRight: '30px',
        },
        cell: ({ cuda_core }) => <span>{`${cuda_core ?? '0'} Cores`}</span>,
      },
      {
        label: t('node.vram.label'),
        selector: 'vram',
        headStyle: {
          flex: '0 0 100px',
          minWidth: '100px',
          justifyContent: 'center',
          paddingRight: '28px',
        },
        bodyStyle: {
          flex: '0 0 100px',
          minWidth: '100px',
          justifyContent: 'center',
          color: '#121619',
          paddingRight: '28px',
        },
        cell: ({ gpu_mem }) => <span>{`${gpu_mem ?? '0'} MB`}</span>,
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
        cell: ({ total, alloc, used }) => {
          const { percentage: allocPercent } = calPercent(total, alloc);
          const { percentage: usedPercent } = calPercent(total, used);
          return (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <AllStorageStack
                label='할당'
                labelValue={`${alloc} EA`}
                totalSize={`${total} EA`}
                percentage={allocPercent}
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
                labelValue={`${used} EA`}
                totalSize={`${total} EA`}
                percentage={usedPercent}
              />
            </div>
          );
        },
      },
    ];
  }
};

/**
 * GPU 할당 상태 컴포넌트
 * @component
 * @example
 *
 * return (
 *  <GPUAllocationStatus />
 * );
 */
const defaultObject = {
  name: '-',
  total: 0,
  cuda_core: 0,
  gpu_mem: 0,
  alloc: 0,
  used: 0,
};
const defaultArr = [defaultObject, defaultObject];

const GPUAllocationStatus = ({ isLoading, gpu, gpuList }) => {
  const { t } = useTranslation();
  const { total, used, alloc, avail } = gpu;

  // 테이블 데이터
  const rateListTarget = useMemo(() => {
    return {
      label: t('allocationRateByGpuModel.label'),
      value: 'model',
    };
  }, [t]);

  const { percentage } = calPercent(total, used);
  const labelList = useMemo(() => {
    return [
      {
        label: t('total.label'),
        value: `${total} EA`,
      },
      {
        label: t('allocateGpu.label'),
        value: `${alloc} EA`,
      },
      {
        label: t('storageAvailable.label'),
        value: `${avail} EA`,
      },
      {
        label: t('enable.label'),
        value: `${used} EA`,
      },
    ];
  }, [alloc, avail, t, total, used]);

  return (
    <NodeDashboardTemplate
      pieChartRender={
        <StoragePieChart
          title={t('node.gpu.allocate.label')}
          percentage={percentage}
          labelList={labelList}
        />
      }
      listRender={
        <AdminNodeRateList
          title={t('allocationRateByGpuModel.label')}
          listData={isLoading ? defaultArr : gpuList}
          columns={getColumns(rateListTarget.value, t)}
        />
      }
    />
  );
};

export default GPUAllocationStatus;
