import { useCallback, useEffect, useRef, useState } from 'react';
import { useHistory } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';

import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
import { getEdgeWorkers } from '@src/apis/flightbase/edge';
import { loadModalComponent } from '@src/modal';

import CPUAllocationStatus from './CPUServerTab/CPUAllocationStatus';
import RamUsageStatus from './CPUServerTab/RamUsageStatus';
import GPUAllocationStatus from './GPUServerTab/GPUAllocationStatus';
import InstanceDetail from './InstanceDetail';
import NodeTable from './NodeTable';
import EdgeWorkerSection from './EdgeWorkerSection';

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
  // Edge 워커는 stat grid 집계용으로만 조회(테이블은 EdgeWorkerSection 자체 fetch). 10s 폴링.
  const [edgeWorkers, setEdgeWorkers] = useState([]);
  const [segment, setSegment] = useState('all'); // all | cluster | edge

  const isLoading = useRef(true);
  const history = useHistory();

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

  // Edge 워커: 부모가 소유·폴링(단일 소스) → stat grid + EdgeWorkerSection 공용.
  // 세그먼트가 'cluster'라 EdgeWorkerSection 이 안 보여도 카운트는 유지되도록 부모가 폴링.
  const edgeFetchingRef = useRef(false);
  const fetchEdge = useCallback(async () => {
    if (edgeFetchingRef.current) return; // 중첩 방지
    edgeFetchingRef.current = true;
    try {
      const res = await getEdgeWorkers();
      if (res.status === STATUS_SUCCESS) setEdgeWorkers(res.result || []);
    } finally {
      edgeFetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    fetchEdge();
    const iv = setInterval(fetchEdge, 10000);
    return () => clearInterval(iv);
  }, [fetchEdge]);

  const nodeList = nodeInfo.node_list || [];
  const k8sTotal = nodeList.length;
  const k8sOnline = nodeList.filter((n) => n.status === 'Ready').length;
  const edgeTotal = edgeWorkers.length;
  const edgeOnline = edgeWorkers.filter(
    (w) => w.conn_status === 'online',
  ).length;
  const gpuTotal = nodeInfo?.usage?.gpu?.total ?? 0;
  const gpuUsed = nodeInfo?.usage?.gpu?.used ?? 0;
  // K8s 노드 라벨은 P4b(후속) — 현재는 edge embedded 라벨만 집계.
  const labelCount = edgeWorkers.reduce(
    (a, w) => a + (w.labels?.length || 0),
    0,
  );

  const showCluster = segment !== 'edge';
  const showEdge = segment !== 'cluster';

  const STAT_BOXES = [
    { key: 'total', label: t('nodes.stat.total'), value: k8sTotal + edgeTotal },
    {
      key: 'k8s',
      label: t('nodes.stat.k8s'),
      value: k8sTotal,
      extra: <span className={cx('stat-on')}>● {k8sOnline}</span>,
    },
    {
      key: 'edge',
      label: t('nodes.stat.edge'),
      value: edgeTotal,
      edge: true,
      extra: (
        <>
          <span className={cx('stat-on')}>● {edgeOnline}</span>{' '}
          <span className={cx('stat-off')}>○ {edgeTotal - edgeOnline}</span>
        </>
      ),
    },
    {
      key: 'gpu',
      label: t('nodes.stat.gpu'),
      value: `${gpuUsed} / ${gpuTotal}`,
    },
    { key: 'labels', label: t('nodes.stat.labels'), value: labelCount },
  ];

  return (
    <div>
      <PageHeader
        title={t('nodes.label')}
        rightComponent={
          <div className={cx('head-actions')}>
            <ButtonV2
              type='outline'
              size='s'
              label={t('edgeApi.title')}
              onClick={() => history.push('/admin/nodes/edge/api-spec')}
            />
            <ButtonV2
              colorType='blue'
              size='s'
              label={t('edge.register.title')}
              onClick={() => history.push('/admin/nodes/edge/new')}
            />
          </div>
        }
      />
      <div className={cx('content')}>
        <div className={cx('stat-grid')}>
          {STAT_BOXES.map((s) => (
            <div key={s.key} className={cx('stat-box')}>
              <div className={cx('stat-label')}>{s.label}</div>
              <div className={cx('stat-value', { edge: s.edge })}>
                {s.value} {s.extra}
              </div>
            </div>
          ))}
        </div>

        <div
          className={cx('segments')}
          role='tablist'
          aria-label={t('nodes.label')}
        >
          {['all', 'cluster', 'edge'].map((s) => (
            <button
              key={s}
              type='button'
              role='tab'
              aria-selected={segment === s}
              className={cx('segment', { active: segment === s })}
              onClick={() => setSegment(s)}
            >
              {t(`nodes.segment.${s}`)}
            </button>
          ))}
        </div>

        {showCluster && (
          <>
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
          </>
        )}
        {showEdge && (
          <EdgeWorkerSection
            workers={edgeWorkers}
            refetch={fetchEdge}
            hideRegister
          />
        )}
      </div>
    </div>
  );
}

export default AdminNodeContent;
