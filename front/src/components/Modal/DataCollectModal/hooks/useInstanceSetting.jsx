import { useCallback, useState } from 'react';

const calSelectedInstance = (instanceList) => {
  const findInstanceList = instanceList.find((info) => info.front.isCheck);
  return findInstanceList;
};

const calCheckList = (checkValue, instance_id, instanceList) => {
  const shallowInstanceList = instanceList.slice();
  const checkList = shallowInstanceList.map((info) => {
    if (info.instance_id === instance_id) {
      return {
        ...info,
        front: {
          isCheck: checkValue,
          value: 0,
        },
      };
    } else {
      return {
        ...info,
        front: {
          isCheck: false,
          value: 0,
        },
      };
    }
  });
  return checkList;
};

const useInstanceSetting = () => {
  const [instanceList, setInstanceList] = useState([]);

  const selectedInstance = calSelectedInstance(instanceList);
  const handleSelectInstance = useCallback(
    (checkValue, instance_id) => {
      const checkList = calCheckList(checkValue, instance_id, instanceList);
      setInstanceList(checkList);
    },
    [instanceList],
  );

  const handleGpuValue = useCallback(
    (value, instance_id) => {
      const checkList = calCheckList(true, instance_id, instanceList);
      const gpuObj = checkList.find((info) => info.instance_id === instance_id);
      gpuObj.front.value = value;
      setInstanceList(checkList);
    },
    [instanceList],
  );

  return {
    selectedInstance,
    instanceList,
    setInstanceList,
    handleSelectInstance,
    handleGpuValue,
  };
};

export default useInstanceSetting;
