import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';

import { callApi, STATUS_FAIL } from '@src/network';
import { loadModalComponent } from '@src/modal';

import CPUAllocationStatus from './CPUServerTab/CPUAllocationStatus';
import RamUsageStatus from './CPUServerTab/RamUsageStatus';
import GPUAllocationStatus from './GPUServerTab/GPUAllocationStatus';
import InstanceDetail from './InstanceDetail';
import NodeTable from './NodeTable';

import { calIsIntervalErrorToast, executeWithLogging } from '@src/utils';
import { initial } from './util';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminNodeContent.module.scss';

const cx = classNames.bind(style);

const calCpuHostList = (node_list, name) => {
  const nodeList = node_list.slice();
  const hostList = nodeList.reduce((acc, cur) => {
    if (cur.cpu_info.cpu_model === name) {
      acc.push(cur.hostname);
    }
    return acc;
  }, []);
  return hostList;
};

let errorCount = 0;
const getNodeInfo = async (isFetching, setNodeInfo) => {
  const isIntervalError = calIsIntervalErrorToast(errorCount);
  if (isIntervalError) return;

  const { result, status } = await callApi({
    url: 'nodes/node-info',
    method: 'get',
  });

  if (status === STATUS_FAIL) {
    errorCount++;
    console.error('errorCount : ', errorCount);
    return;
  }
  errorCount = 0;

  const { node_list, usage } = result;
  const chageCpuList = Object.keys(usage.cpu.detail).map((key) => ({
    ...usage.cpu.detail[key],
    name: key,
  }));

  const usageCpuDetailList = chageCpuList.reduce((acc, cur) => {
    const hostList = calCpuHostList(node_list, cur.name);
    const newCpuObj = {
      ...cur,
      hostList,
    };
    acc.push(newCpuObj);
    return acc;
  }, []);

  const chageGpuList = Object.keys(usage.gpu.detail).map((key) => ({
    ...usage.gpu.detail[key],
    name: key,
  }));

  // ** 객체 풀려고 반복문을 몇번을 돌리냐 **
  const chageMemList = Object.keys(usage.mem.detail).map((key) => ({
    ...usage.mem.detail[key],
    name: key,
  }));

  const transformedInstanceData = Object.values(result.usage?.instance).map(
    (item) => {
      const allocateWorkspaceListArray = Object.entries(
        item.allocate_workspace_list,
      ).map(([workspace_name, { instance_count }]) => ({
        workspace_name,
        instance_count,
      }));

      return {
        ...item,
        allocate_workspace_list: allocateWorkspaceListArray,
      };
    },
  );

  setNodeInfo({
    ...result,
    usage: {
      ...result.usage,
      cpu: {
        ...result.usage.cpu,
        detail: usageCpuDetailList,
      },
      gpu: {
        ...result.usage.gpu,
        detail: chageGpuList,
      },
      mem: {
        ...result.usage.mem,
        detail: chageMemList,
      },
      instanceList: transformedInstanceData,
    },
  });
  isFetching.current = false;
};

function AdminNodeContent() {
  const { t } = useTranslation();

  const [nodeInfo, setNodeInfo] = useState(initial);
  const [statusList, setStatusList] = useState([]);

  const isLoading = useRef(true);

  useEffect(() => {
    loadModalComponent('SETTING_VIRTUAL_NODE');

    getNodeInfo(isLoading, setNodeInfo);
    const intervalId = setInterval(() => {
      executeWithLogging(() => getNodeInfo(isLoading, setNodeInfo));
    }, 1000);

    // Cleanup interval on component unmount
    return () => {
      errorCount = 0;
      isLoading.current = true;
      clearInterval(intervalId);
    };
  }, []);

  const calNodeListLength = (nodeList) => {
    if (!nodeList) return 0;
    return nodeList.length;
  };
  const nodeListLength = calNodeListLength(nodeInfo.node_list);

  useEffect(() => {
    if (nodeListLength === 0) return;
    const statusList = nodeInfo.node_list.map((el) => {
      return {
        nodeId: el.id,
        status: el.status,
      };
    });
    setStatusList(statusList);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeListLength]);

  return (
    <div>
      <PageHeader title={t('nodes.label')} />
      <div className={cx('content')}>
        <CPUAllocationStatus
          isLoading={isLoading.current}
          cpu={
            nodeInfo
              ? nodeInfo.usage.cpu
              : { total: 0, used: 0, alloc: 0, avail: 0 }
          }
          nodeList={nodeInfo.usage.cpu.detail}
        />
        <GPUAllocationStatus
          isLoading={isLoading.current}
          gpu={
            nodeInfo
              ? nodeInfo.usage.gpu
              : { total: 0, used: 0, alloc: 0, avail: 0 }
          }
          gpuList={nodeInfo.usage.gpu.detail}
        />
        <RamUsageStatus
          isLoading={isLoading.current}
          ram={
            nodeInfo
              ? nodeInfo.usage.mem
              : { total: 0, used: 0, alloc: 0, avail: 0 }
          }
          nodeList={nodeInfo.usage.mem.detail}
        />
        <InstanceDetail
          isLoading={isLoading.current}
          instanceList={nodeInfo ? nodeInfo.usage.instanceList : []}
        />
        <NodeTable
          nodeList={nodeInfo.node_list}
          statusList={statusList}
          setStatusList={setStatusList}
        />
      </div>
    </div>
  );
}

export default AdminNodeContent;
