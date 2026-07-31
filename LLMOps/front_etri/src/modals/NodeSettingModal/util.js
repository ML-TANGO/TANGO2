import { callApi } from '@src/network';

// ** 초기 값 **
export const changeInitialTypeValue = (type, free) => {
  return {
    instance_name: '',
    instance_count: 0,
    instance_type: type,
    instance_validation: false,
    instance_check_validation: false,
    gpu_name: type === 'CPU' ? null : '',
    gpu_total: type === 'CPU' ? null : 0,
    gpu_vram: type === 'CPU' ? null : 1,
    gpu_group_id: null,
    gpu_allocate: null,
    cpu_allocate: free.cpu,
    ram_allocate: free.ram,
    free_cpu: free.cpu,
    free_ram: free.ram,
  };
};

// ** 폼 변경 시에 obj 값 설정 **
export const changeForm = (instanceList, type, free) => {
  const shallowCopyList = instanceList.slice();
  const pushObj = changeInitialTypeValue(type, free);
  shallowCopyList.push(pushObj);
  return shallowCopyList;
};

export const calRemoveNvidia = (text) => {
  return text.replace(/NVIDIA\s*/g, '');
};

// ** Instance 이름 받아오는 함수 **
export const getInstanceName = (instanceInfo) => {
  const { instance_type, gpu_name, cpu_allocate, gpu_allocate, ram_allocate } =
    instanceInfo;

  if (instance_type === 'GPU') {
    const changedGpuName = calRemoveNvidia(gpu_name);
    return `${gpu_name.length ? changedGpuName : '(GPU name)'}.${
      gpu_allocate ? gpu_allocate : '(GPU allocate)'
    }.${cpu_allocate ? cpu_allocate : '(vCpu allocate)'}.${
      ram_allocate ? ram_allocate : '(RAM allocate)'
    }`;
  }

  if (instance_type === 'CPU') {
    return `CPU.${cpu_allocate ? cpu_allocate : '(CPU allocate)'}.${
      ram_allocate ? ram_allocate : '(RAM allocate)'
    }`;
  }
};

// ** GPU 설정 List 만들어주는 함수 **
export const calFreeGpuList = (gpuIdList, node_gpu_list) => {
  const shallowCopyList = gpuIdList.slice();
  const freeGpuList = shallowCopyList.map((id) => {
    const { name, group_id, total, vram } = node_gpu_list[id];
    return {
      gpu_name: name,
      gpu_total: total,
      gpu_vram: vram,
      gpu_group_id: group_id,
      isCheck: false,
    };
  });
  return freeGpuList;
};

// ** CPU가 할당되어 있는지 체크해주는 함수 **
export const isCheckCpuList = (instanceList) => {
  if (!instanceList.length) return false;
  const shallowCopList = instanceList.slice();
  const cpuTypeValue = shallowCopList.find((el) => el.instance_type === 'CPU');
  return !!cpuTypeValue;
};

export const isCheckGpuListValue = (freeGpuList) => {
  if (!freeGpuList) return false;
  const shallowCopyList = freeGpuList.slice();
  const findIsCheckTrue = shallowCopyList.find((el) => el.isCheck === true);
  return !!findIsCheckTrue;
};

// ** 할당될 GPU 체크 함수 **
export const isCheckGpuList = (freeGpuList) => {
  if (!freeGpuList) return false;
  if (freeGpuList.length > 0) return false;
  return true;
};

// ** [CPU, GPU, RAM] 자원 타입 **
export const RESOURCE_TYPE = {
  CPU: 'cpu_allocate',
  GPU: 'gpu_allocate',
  RAM: 'ram_allocate',
};

// ** 인스턴스 리스트 선택된 뒤로 삭제 함수 **
export const calDeleteInstanceList = (instanceList, idx) => {
  const shallowCopyList = instanceList.slice();
  const deleteCopyList = shallowCopyList.splice(shallowCopyList, idx);
  return deleteCopyList;
};

// ** [CPU, GPU, RAM] 할당 변경 계산 함수 **
const calResourceAllocate = (idx, value, instanceList, resourceType) => {
  const shallowCopyList = instanceList.slice();
  const updateItem = shallowCopyList[idx];
  updateItem[resourceType] = value;
  updateItem.instance_validation = false;
  updateItem.instance_check_validation = false;
  return shallowCopyList;
};

// ** [CPU, GPU, RAM] 자원 변경 핸들러 **
export const handleResource = (idx, value, setInstanceList, resourceType) => {
  setInstanceList((prev) => {
    const { instance_list } = prev;
    const deleteInstanceList = calDeleteInstanceList(instance_list, idx + 1);
    const changeInstanceList = calResourceAllocate(
      idx,
      value,
      deleteInstanceList,
      resourceType,
    );
    return {
      ...prev,
      instance_list: changeInstanceList,
    };
  });
};

// ** 유효성 검사 POST API **
export const postInstanceValidation = async (nodeId, instanceList) => {
  const { result } = await callApi({
    url: 'nodes/instance-validation',
    method: 'post',
    body: {
      node_id: nodeId,
      instance_list: instanceList,
    },
  });
  return { result };
};

// ** 유효성 검사 POST API **
export const postValidation = async (nodeId, instanceList, setInstanceList) => {
  const copyInstanceList = instanceList.slice();
  const filterInstanceList = copyInstanceList.map((info) => {
    const instanceName = getInstanceName(info);
    const { instance_validation, instance_count } = info;
    return {
      instance_name: instanceName,
      instance_type: info.instance_type,
      instance_count: instance_validation ? instance_count : null,
      gpu_group_id: info.gpu_group_id,
      gpu_allocate: info.gpu_allocate,
      cpu_allocate: info.cpu_allocate,
      ram_allocate: info.ram_allocate,
    };
  });

  const { result } = await callApi({
    url: 'nodes/instance-validation',
    method: 'post',
    body: {
      node_id: nodeId,
      instance_list: filterInstanceList,
    },
  });

  const { instance_list, last_free_resource, node_gpu_list } = result;

  // ** freeGpu 값 formInstanceList 상태에서 관리 **
  const freeGpuList = calFreeGpuList(
    last_free_resource.gpu_id_list,
    node_gpu_list,
  );

  // ** CPU 값 체크 **
  const isCpuValue = isCheckCpuList(instance_list);

  // ** instanceList 0일 때도 고려**
  const instanceListZero = changeForm([], 'GPU', last_free_resource);

  const copyList = instance_list.slice();
  const newInstanceList = copyList.map((el) => {
    return {
      ...el,
      instance_check_validation: true,
    };
  });

  setInstanceList({
    ...result,
    instance_list:
      instance_list.length === 0 ? instanceListZero : newInstanceList,
    freeGpuList,
    isCpuValue,
  });
};

// ** 유효성 검사 API 효출 핸들러 **
export const handleValidate = async (
  nodeId,
  instanceInfo,
  instanceList,
  setInstanceList,
) => {
  const { instance_type, gpu_name, gpu_allocate, cpu_allocate, ram_allocate } =
    instanceInfo;
  if (instance_type === 'GPU') {
    if (!gpu_name || !gpu_allocate) return;
  }

  if (!cpu_allocate || !ram_allocate) return;

  await postValidation(nodeId, instanceList, setInstanceList);
};

// ** 추가 버튼 유효성 검사 **
export const isValidateAddBtn = (
  idx,
  instanceList,
  freeGpuList,
  last_free_resource,
) => {
  if (idx !== instanceList.length - 1) return false;

  const { cpu, ram } = last_free_resource;
  if (cpu === 0 || ram === 0) return false;

  const isCheckCpuValue = isCheckCpuList(instanceList);
  if (!isCheckCpuValue || freeGpuList.length > 0) return true;

  return false;
};

// ** instance last index 확인 계산 함수 **
export const calLastInstanceListIndex = (instanceList, idx) => {
  if (instanceList.length - 1 === idx) return true;
  return false;
};
