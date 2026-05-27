import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';

const useDatasetResource = ({ preprocessing_id }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const [gpuInfo, setGpuInfo] = useState({
    name: '',
    max: 0,
    used: '',
  });
  const [gpuClusterSelectedOption, setGpuClusterSelectedOption] = useState(1);
  const [gpuClusterList, setGpuClusterList] = useState([]);
  const [selectedGpuList, setSelectedGpuList] = useState([]);
  const [podGpuGcd, setPodGpuGcd] = useState(0);
  const [gpuUsingError, setGpuUsingError] = useState('');
  const [gpuClusterType, setGpuClusterType] = useState([]);
  const [selectedGpuClusterType, setSelectedGpuClusterType] = useState(0);
  const [originalGpuClusterList, setOriginalGpuClusterList] = useState(null);

  const handleGpuCnt = ({ value }) => {
    setGpuInfo((prev) => ({
      ...prev,
      used: value,
    }));
  };

  const handleGpuClusterOption = (value) => {
    setGpuClusterSelectedOption(parseInt(value));
  };

  const handleSelectedGpuCluster = ({
    nodeName,
    gpu_uuid,
    used,
    originUsed,
  }) => {
    if (Number(gpuInfo.used) === selectedGpuList.length && used !== 2) {
      return;
    }

    setGpuClusterList((prevGpuClusterList) =>
      prevGpuClusterList.map((cluster) => ({
        ...cluster,
        gpuList: cluster.gpuList.map((gpu) => {
          if (gpu.gpu_uuid === gpu_uuid) {
            return {
              ...gpu,
              used: gpu.used === 0 || gpu.used === 1 ? 2 : originUsed,
            };
          }
          return gpu;
        }),
      })),
    );

    setSelectedGpuList((prevSelectedGpuList) => {
      let updatedselectedGpuList = [...prevSelectedGpuList];

      if (used === 0 || used === 1) {
        updatedselectedGpuList.push({ node_name: nodeName, gpu_uuid });
      } else {
        updatedselectedGpuList = updatedselectedGpuList.filter(
          (gpu) => !(gpu.node_name === nodeName && gpu.gpu_uuid === gpu_uuid),
        );
      }

      return updatedselectedGpuList;
    });

    // submitBtnCheck();
  };

  const handleGpuClusterType = (value) => {
    setSelectedGpuClusterType(parseInt(value, 10));
  };

  const checkIsGpuClusterTypeDiff = (prevGpuCluster, curGpuCluster) => {
    const sortFn = (a, b) => {
      if (a.gpu_count !== b.gpu_count) {
        return a.gpu_count - b.gpu_count;
      } else {
        return a.server - b.server;
      }
    };

    const sortedPrev = [...prevGpuCluster].sort(sortFn);
    const sortedCur = [...curGpuCluster].sort(sortFn);

    if (sortedPrev.length !== sortedCur.length) {
      return false;
    }

    for (let i = 0; i < sortedPrev.length; i++) {
      const prevItem = sortedPrev[i];
      const curItem = sortedCur[i];

      if (
        prevItem.gpu_count !== curItem.gpu_count ||
        prevItem.server !== curItem.server ||
        prevItem.status !== curItem.status
      ) {
        return false;
      }
    }

    return true;
  };

  const updateGpuClusterType = (gpuClusterTypeList) => {
    const gpuClusterTypes = gpuClusterTypeList.map(
      ({ gpu_count, server, status }, index) => ({
        label: `${gpu_count}-GPU PODx${server}`,
        value: index,
        desc: status
          ? `${t('gpuRecommandTime.desc')}`
          : `${t('gpuWarningTime.desc')}`,
        descStatus: status,
        gpu_count,
        server,
        status,
      }),
    );

    const isSameGpuClusterType = checkIsGpuClusterTypeDiff(
      gpuClusterType,
      gpuClusterTypes,
    );

    if (gpuClusterType.length && !isSameGpuClusterType) {
      dispatch(
        openConfirm({
          title: 'gpuClusterCategory.label',
          content: 'gpuTypePopupfirst.desc',
          submit: {
            text: 'confirm.label',
          },
          cancel: {
            text: 'cancel.label',
          },
          contentCustomStyle: {
            color: 'rgba(116, 116, 116, 1)',
          },
        }),
      );
    }
    setGpuClusterType(gpuClusterTypes);
    setSelectedGpuClusterType(0);
  };

  const fetchNodeGpuList = async () => {
    if (
      gpuClusterSelectedOption === 1 ||
      gpuInfo.used < 2 ||
      (gpuInfo.used !== selectedGpuList.length && selectedGpuList.length > 0)
    )
      return;

    const uuid = selectedGpuList.map(({ gpu_uuid }) => gpu_uuid);

    const response = await callApi({
      url: `preprocessing/option/gpu-cluster`,
      method: 'POST',
      body: {
        // project_id: Number(projectId),
        preprocessing_id: preprocessing_id,
        gpu_count: Number(gpuInfo.used),
        gpu_select: selectedGpuList.length > 0 ? selectedGpuList : [],
      },
    });

    const { status, result } = response;
    const { gpu_cluster_list, gpu_cluster_cases } = result;

    if (gpu_cluster_list) {
      const nodes = Object.keys(gpu_cluster_list);
      const list = [];

      nodes.forEach((node) => {
        list.push({
          nodeName: node,
          gpuList: gpu_cluster_list[node].map(
            ({ gpu_name, gpu_uuid, used }) => ({
              gpu_name,
              gpu_uuid,
              used: uuid.includes(gpu_uuid) ? 2 : used,
              originUsed: used,
            }),
          ),
        });
      });

      setGpuClusterList(list);
      setOriginalGpuClusterList(gpu_cluster_list);
    }

    if (gpu_cluster_cases) {
      updateGpuClusterType(gpu_cluster_cases);
    }
  };

  const fetchGpuClusterType = useCallback(async () => {
    if (gpuInfo.used > 1 && gpuClusterSelectedOption === 1) {
      const response = await callApi({
        url: `preprocessing/option/gpu-cluster-auto?preprocessing_id=${preprocessing_id}&gpu_count=${gpuInfo.used}`,
        method: 'GET',
      });
      const { status, result } = response;

      if (status === STATUS_SUCCESS) {
        updateGpuClusterType(result);
      }
    }
  }, [gpuInfo, gpuClusterSelectedOption, preprocessing_id]);

  const calculatePodGpuCount = () => {
    const podGpuCount = {};

    gpuClusterList.forEach(({ nodeName, gpuList }) => {
      podGpuCount[nodeName] = 0;
      gpuList.forEach(({ used }) => {
        if (used === 2) {
          podGpuCount[nodeName] += 1;
        }
      });
    });

    function gcd(a, b) {
      while (b !== 0) {
        let temp = b;
        b = a % b;
        a = temp;
      }
      return a;
    }

    // 배열의 숫자들의 최대공약수를 구하는 함수
    function findGCD(arr) {
      if (arr.length === 0) return 0;

      let result = arr[0];

      for (let i = 1; i < arr.length; i++) {
        result = gcd(result, arr[i]);

        if (result === 1) {
          return 1;
        }
      }

      return result;
    }

    const totalCount = findGCD(Object.values(podGpuCount));
    setPodGpuGcd(totalCount);
  };

  const checkSelectedUsedGpu = () => {
    const uuid = selectedGpuList.map(({ gpu_uuid }) => gpu_uuid);
    let usedCount = 0;

    gpuClusterList.forEach(({ gpuList }) => {
      gpuList.forEach(({ gpu_uuid, originUsed }) => {
        if (uuid.includes(gpu_uuid) && originUsed === 1) {
          usedCount += 1;
          setGpuUsingError(`${t('gpuUsing.warning')}`);
        }
      });
    });

    if (usedCount === 0) {
      setGpuUsingError('');
    }
  };

  useEffect(() => {
    fetchGpuClusterType();
  }, [gpuInfo, gpuClusterSelectedOption, fetchGpuClusterType]);

  useEffect(() => {
    calculatePodGpuCount();
  }, [gpuClusterList]);

  useEffect(() => {
    checkSelectedUsedGpu();
    fetchNodeGpuList();
  }, [selectedGpuList]);

  useEffect(() => {
    setSelectedGpuList([]);
    fetchNodeGpuList();
  }, [gpuInfo, gpuClusterSelectedOption]);

  return {
    gpuInfo,
    gpuClusterList,
    gpuClusterSelectedOption,
    podGpuGcd,
    gpuUsingError,
    gpuClusterType,
    selectedGpuClusterType,
    originalGpuClusterList,
    selectedGpuList,
    fetchGpuClusterType,
    handleGpuCnt,
    handleGpuClusterOption,
    handleSelectedGpuCluster,
    handleGpuClusterType,
    setGpuInfo,
  };
};

export default useDatasetResource;
