import { useCallback, useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';

// Components

import ToolGpuAllocateModalContent from '@src/components/modalContents/ToolGpuAllocateModalContent';

// Actions
import { openConfirm } from '@src/store/modules/confirm';
import { closeModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// Utils
import { errorToastMessage } from '@src/utils';

function ToolPasswordChangeModal({ type, data: modalData }) {
  const { toolId, isReset, t, projectId } = modalData;

  // Redux Hooks
  const dispatch = useDispatch();

  const [validate, setValidate] = useState(false);
  const [messageType, setMessageType] = useState(0);
  const [message, setMessage] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [maxValue, setMaxValue] = useState(0);
  const [gpuClusterSelectedOption, setGpuClusterSelectedOption] = useState(1);
  const [dockerImageList, setDockerImageList] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [gpuClusterList, setGpuClusterList] = useState([]);
  const [gpuClusterType, setGpuClusterType] = useState([]);
  const [selectedGpuClusterType, setSelectedGpuClusterType] = useState(0);
  const [selectedGpuList, setSelectedGpuList] = useState([]);
  const [podGpuGcd, setPodGpuGcd] = useState(0);
  const [gpuUsingError, setGpuUsingError] = useState('');
  const [instanceType, setInstanceType] = useState('GPU');
  const [originalGpuClusterList, setOriginalGpuClusterList] = useState(null);
  const [instanceInfo, setInstanceInfo] = useState({
    resource_name: '',
  });

  const [datasetList, setDatasetList] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);

  const handleDataset = useCallback((v) => {
    setSelectedDataset(v.id);
  }, []);

  /**
   * gpu 할당모달
   */
  const gpuAllocationConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'gpuAllocation.label',
        content: 'gpuAllocationPopup.message',
        submit: {
          text: 'accept.label',
          func: () => {
            // onDelete();
            postGpuData();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteDeploymentPopup.content.message'),
        // confirmMessage: t('deleteDeploymentPopup.title.label'),
      }),
    );
  };

  const submitBtnCheck = useCallback(() => {
    let validateCount = 0;

    if (!selectedImage || !selectedDataset) {
      validateCount += 1;
    }
    if (typeof inputValue !== 'number') {
      validateCount += 1;
    }
    if (
      gpuClusterSelectedOption === 0 &&
      inputValue > 1 &&
      inputValue !== selectedGpuList.length
    ) {
      validateCount += 1;
    }
    if (validateCount !== 0) {
      setValidate(false);
      return;
    }

    setValidate(true);
  }, [
    selectedImage,
    inputValue,
    gpuClusterSelectedOption,
    selectedGpuList,
    selectedDataset,
  ]);

  const onSubmit = async (callback) => {
    dispatch(closeModal('TOOL_GPU_ALLOCATE'));

    const body = {
      project_tool_id: toolId,
      gpu_count: inputValue,
      action: 'on',
      dataset_id: selectedDataset,
    };

    body.docker_image_id = selectedImage;

    if (parseInt(inputValue) > 1) {
      body.gpu_cluster_auto = gpuClusterSelectedOption === 1 ? true : false;

      const { gpu_count, status, server } =
        gpuClusterType[selectedGpuClusterType];

      if (gpuClusterSelectedOption === 1) {
        // GPU 클러스터 자동설정
        body.gpu_auto_select = { gpu_count, server, status };
        body.gpu_cluster_case_old = gpuClusterType.map(
          ({ gpu_count, server, status }) => ({ gpu_count, server, status }),
        );
      } else {
        // GPU 클러스터 수동설정
        body.gpu_select = selectedGpuList;
        body.pod_per_gpu = gpu_count;
        body.gpu_cluster_list_old = originalGpuClusterList;
      }
    }

    const response = await callApi({
      url: 'projects/control_training_tool',
      method: 'PUT',
      body,
    });

    const { status, message, error, result } = response;

    if (!result) {
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

      fetchGpuClusterType();

      return false;
    }

    if (status === STATUS_SUCCESS) {
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  const calFooterMessage = (selectedImage, selectedDataset, inputValue) => {
    if (!selectedImage) return '도커 이미지를 선택해 주세요.';
    if (!selectedDataset) return '데이터셋을 선택해 주세요.';
    // if (!inputValue && instanceType === 'GPU') return 'GPU를 할당해 주세요.';
    return '';
  };
  const footerMessage = calFooterMessage(
    selectedImage,
    selectedDataset,
    inputValue,
  );

  const handleGpuClusterOption = (value) => {
    setGpuClusterSelectedOption(parseInt(value));
  };

  const postGpuData = async () => {
    const body = {
      project_tool_id: toolId,
      gpu_count: inputValue,
    };

    const response = await callApi({
      url: 'projects/tool-option',
      method: 'post',
      body,
    });

    const { status, error, message } = response;

    if (status === STATUS_SUCCESS) {
      console.log('success gpu data');
    } else {
      errorToastMessage(error, message);
    }
  };

  const selectImageHandler = (value) => {
    setSelectedImage(value.value);
  };

  const getGpuData = async () => {
    // /tool-gpu/{project_id} get -> 사용가능한 gpu 수
    // /tool-gpu  post -> { "project_tool_id" :   , "gpu_count" : }  -> gpu 수정

    const response = await callApi({
      url: `options/project/tool?project_id=${projectId}&project_tool_id=${toolId}`,
      method: 'get',
    });

    const { status, error, message, result } = response;

    if (status === STATUS_SUCCESS) {
      const {
        project_gpu_total: total,
        tool_gpu_count: count,
        image_list: dockerList = [],
        instance_type,
        instance_info,
        dataset_list,
      } = result;

      const transfromDatasetList = dataset_list.map((info) => {
        return {
          ...info,
          label: info.name,
          value: info.id,
        };
      });

      const initialSelectedImage = [];

      const newDockerList = dockerList.map((v) => {
        if (v.name === 'jf-default') {
          initialSelectedImage.push({
            label: v.name,
            value: v.id,
          });
        }
        return {
          label: v.name,
          value: v.id,
        };
      });
      setMaxValue(total);
      setDockerImageList(newDockerList);
      setSelectedImage(...initialSelectedImage);
      setInstanceType(instance_type);
      setInstanceInfo(instance_info);
      setDatasetList(transfromDatasetList);

      setInputValue(0);
    } else {
      errorToastMessage(error, message);
    }
  };

  const fetchGpuClusterType = useCallback(async () => {
    if (inputValue > 1 && gpuClusterSelectedOption === 1) {
      const response = await callApi({
        url: `projects/gpu-cluster-auto?project_id=${projectId}&gpu_count=${inputValue}`,
        method: 'GET',
      });
      const { status, result } = response;

      if (status === STATUS_SUCCESS) {
        updateGpuClusterType(result);
      }
    }
  }, [inputValue, gpuClusterSelectedOption, projectId]);

  const handleGpuClusterType = (value) => {
    setSelectedGpuClusterType(parseInt(value, 10));
  };

  /// ---------------------------  ///
  const handleSelectedGpuCluster = ({
    nodeName,
    gpu_uuid,
    used,
    originUsed,
  }) => {
    if (Number(inputValue) === selectedGpuList.length && used !== 2) {
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

  const onChangeInputValue = (value) => {
    if (value > 0) {
      setMessageType(1);
    } else {
      setMessageType(0);
    }
    setInputValue(value);
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
      inputValue < 2 ||
      (inputValue !== selectedGpuList.length && selectedGpuList.length > 0)
    )
      return;

    const uuid = selectedGpuList.map(({ gpu_uuid }) => gpu_uuid);

    const response = await callApi({
      url: `projects/gpu-cluster`,
      method: 'POST',
      body: {
        project_id: Number(projectId),
        gpu_count: Number(inputValue),
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

  useEffect(() => {
    getGpuData();
  }, []);

  useEffect(() => {
    submitBtnCheck();
  }, [inputValue, selectedImage, selectedGpuList, submitBtnCheck]);

  useEffect(() => {
    fetchGpuClusterType();
  }, [inputValue, gpuClusterSelectedOption, fetchGpuClusterType]);

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
  }, [inputValue, gpuClusterSelectedOption]);

  return (
    <ToolGpuAllocateModalContent
      type={type}
      modalData={modalData}
      messageType={messageType}
      message={message}
      validate={validate}
      onSubmit={onSubmit}
      gpuClusterSelectedOption={gpuClusterSelectedOption}
      inputValue={inputValue}
      onChangeInputValue={onChangeInputValue}
      handleGpuClusterOption={handleGpuClusterOption}
      maxValue={maxValue}
      dockerImageList={dockerImageList}
      selectedImage={selectedImage}
      selectImageHandler={selectImageHandler}
      gpuClusterList={gpuClusterList}
      handleSelectedGpuCluster={handleSelectedGpuCluster}
      handleGpuClusterType={handleGpuClusterType}
      gpuClusterType={gpuClusterType}
      selectedGpuClusterType={selectedGpuClusterType}
      podGpuGcd={podGpuGcd}
      gpuUsingError={gpuUsingError}
      instanceType={instanceType}
      instanceInfo={instanceInfo}
      datasetList={datasetList}
      selectedDataset={selectedDataset}
      handleDataset={handleDataset}
      footerMessage={footerMessage}
    />
  );
}

export default ToolPasswordChangeModal;
