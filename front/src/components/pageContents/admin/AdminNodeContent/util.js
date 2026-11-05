import { callApi } from '@src/network';
import { executeWithLogging } from '@src/utils';

export const initial = {
  node_list: null,
  usage: {
    cpu: {
      avail: 0,
      total: 0,
      alloc: 0,
      used: 0,
      detail: null,
    },
    gpu: {
      avail: 0,
      alloc: 0,
      total: 0,
      used: 0,
    },
    mem: {
      avail: 0,
      total: 0,
      used: 0,
      alloc: 0,
    },
    instanceList: [],
  },
};

export const calInstanceTotalValue = (instanceList) => {
  if (!instanceList) return 0;
  const copyList = instanceList.slice();
  const totalValue = copyList.reduce((acc, cur) => {
    acc += cur.instance_total_count;
    return acc;
  }, 0);
  return totalValue;
};

export const calFindNodeList = (list, id) => {
  const shallowCopyList = list.slice();
  const toggleStatus = shallowCopyList.find((info) => info.nodeId === id);
  return toggleStatus;
};

const calChangeToggleStatus = (setStatusList, nodeId) => {
  setStatusList((prev) => {
    const shallowCopyList = [...prev];
    const findList = shallowCopyList.find((info) => info.nodeId === nodeId);
    findList.status = findList.status === 'Ready' ? 'Not Ready' : 'Ready';
    return shallowCopyList;
  });
};

export const postChangeStatus = async (nodeId, changeStatus, setStatusList) => {
  await executeWithLogging(async () => {
    await callApi({
      url: 'nodes/active',
      method: 'post',
      body: {
        node_id: nodeId,
        active: changeStatus,
      },
    });
  });
  calChangeToggleStatus(setStatusList, nodeId);
};
