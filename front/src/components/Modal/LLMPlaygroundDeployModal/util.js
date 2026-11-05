const zeroSelectedValue = {
  instance_id: null,
  instance_allocate: 0,
  resource_name: '',
  gpu_allocate: 0,
  front: {
    gpuValue: 0,
  },
};

export const calSelectedValue = (modelList) => {
  if (!modelList || modelList.lenght === 0) return zeroSelectedValue;

  const findValue = modelList.find((el) => el.front.isCheck);
  if (!findValue) return zeroSelectedValue;

  return findValue;
};

export const calFindValueReturn = (list, findIndex) => {
  const returnValue = list[findIndex];
  if (!returnValue) return zeroSelectedValue;
  return returnValue;
};

export const calGpuAllocateValue = (selectedValue) => {
  const { front } = selectedValue;
  return front.gpuValue;
};

export const calFindSelectedReturnValue = (instanceList, instance_id) => {
  const findGpuAllocate = instanceList.find(
    (el) => el.instance_id === instance_id,
  );
  if (!findGpuAllocate) return zeroSelectedValue;
  return findGpuAllocate;
};
