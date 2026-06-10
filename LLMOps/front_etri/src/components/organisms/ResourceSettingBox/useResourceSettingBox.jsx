import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import _ from 'lodash';

// Components
import ResourceSettingBox from './ResourceSettingBox';

function useResourceSettingBox({
  sliderData,
  prevSliderData,
  type,
  gpuModels,
  visualStatus,
  gpuCount,
}) {
  const [gpuModelType, setGpuModelType] = useState(0);
  const [gpuTotalCount, setGpuTotalCount] = useState(0);
  const [maxGpuUsageCount, setMaxGpuUsageCount] = useState(0);
  const [gpuTotalCountForRandom, setGpuTotalCountForRandom] = useState(0);
  const [maxGpuUsageCountForRandom, setMaxGpuUsageCountForRandom] = useState(0);
  const [minGpuUsage, setMinGpuUsage] = useState(1); // input number 입력 min 제한용
  const [maxGpuUsage, setMaxGpuUsage] = useState(10000); // input number 입력 max 제한용
  const [isMigModel, setIsMigModel] = useState(false);
  const [gpuUsage, setGpuUsage] = useState('');
  const [gpuUsageError, setGpuUsageError] = useState(null);
  const [modelType, setModelType] = useState(0); // gpu or cpu
  const [cpuModelType, setCpuModelType] = useState(0);

  // slider state
  const [gpuModelListOptions, setGpuModelListOptions] = useState([]);
  const [gpuModelList, setGpuModelList] = useState(null);
  const [cpuModelList, setCpuModelList] = useState([]);
  const [gpuSelectedOptions, setGpuSelectedOptions] = useState([]);
  const [gpuDetailSelectedOptions, setGpuDetailSelectedOptions] = useState([]);
  const [gpuTotalValue, setGpuTotalValue] = useState(1);
  const [gpuRamTotalValue, setGpuRamTotalValue] = useState(1);
  const [gpuDetailValue, setGpuDetailValue] = useState(1);
  const [gpuRamDetailValue, setGpuRamDetailValue] = useState(1);
  const [gpuTotalSliderMove, setGpuTotalSliderMove] = useState(false);
  const [gpuSwitchStatus, setGpuSwitchStatus] = useState(false);
  const [gpuAndRamSliderValue, setGpuAndRamSliderValue] = useState({
    cpu: 1,
    ram: 1,
  });
  const [cpuSwitchStatus, setCpuSwitchStatus] = useState(false);
  const [cpuSelectedOptions, setCpuSelectedOptions] = useState([]);
  const [detailSelectedOptions, setDetailSelectedOptions] = useState([]);
  const [cpuTotalValue, setCpuTotalValue] = useState(1);
  const [ramTotalValue, setRamTotalValue] = useState(1);
  const [cpuDetailValue, setCpuDetailValue] = useState(1);
  const [ramDetailValue, setRamDetailValue] = useState(1);
  const [cpuSliderMove, setCpuSliderMove] = useState(false);
  const [cpuAndRamSliderValue, setCpuAndRamSliderValue] = useState({
    cpu: 1,
    ram: 1,
  });

  const [sliderIsValidate, setSliderIsValidate] = useState(false);

  const isMount = useRef(true);

  /**
   * GPU 모델 관련 상태 정의
   *
   * @param {object} options
   * @param {object} gpuModelList
   * @param {number} gpuUsage
   * @param {string} gpuUsageError
   * @returns
   */
  const gpuModelState = (
    options,
    gpuModelList,
    gpuUsage,
    gpuUsageError = '',
  ) => {
    let migCount = 0;
    let totalCount = 0;
    let avalCount = 0;

    gpuModelList.map(({ type, node_list: nodeList }) => {
      if (type === 'mig') {
        migCount += 1;
      }
      nodeList.map(({ total, aval, selected }) => {
        if (selected) {
          totalCount += total;
          avalCount += aval;
        }
        return true;
      });
      return true;
    });

    if (gpuTotalCountForRandom < totalCount) {
      totalCount = gpuTotalCountForRandom;
    }

    if (maxGpuUsageCountForRandom < avalCount) {
      avalCount = maxGpuUsageCountForRandom;
    }

    let gpuCount = gpuUsage;
    let gpuCountError = gpuUsageError;
    if (modelType === 0 && gpuModelType === 1) {
      if (gpuModelList.length === 0) {
        // gpuCount = '';
        gpuCountError = null;
      } else if (migCount > 0) {
        gpuCount = 1;
        gpuCountError = '';
      }
    } else if (modelType === 0 && gpuModelType === 0) {
      // gpuCount = 1;
      gpuCountError = '';
    }

    const gpuState = {
      gpuModelListOptions: options,
      gpuModelList,
      isMigModel: migCount > 0,
      maxGpuUsageCount: avalCount,
      gpuTotalCount: totalCount,
      gpuUsage: gpuCount,
      gpuUsageError: gpuCountError,
    };
    return gpuState;
  };

  // resource Type Check Hanlder
  const resourceTypeHandler = (type, model) => {
    let token = false;
    type = Number(type);
    model = Number(model);
    const isTrue = (checkbox = []) => {
      if (checkbox.length > 0) {
        const checkTrue = checkbox.filter((check) => check);
        return checkTrue.length > 0;
      }
    };

    if (type === 0) {
      if (model === 1) {
        gpuSelectedOptions.forEach((e, i) => {
          const check = isTrue(Object.values(e));
          if (check) {
            token = true;
            sliderCheck(true);
          }
          if (gpuSelectedOptions.length - 1 === i && !check && !token) {
            sliderCheck(false);
          }
        });
      } else {
        sliderCheck(true);
      }
    } else if (type === 1) {
      if (model === 1) {
        cpuSelectedOptions.forEach((e, i) => {
          const check = isTrue(Object.values(e));
          if (check) {
            token = true;
            sliderCheck(true);
          }
          if (cpuSelectedOptions.length - 1 === i && !check && !token) {
            sliderCheck(false);
          }
        });
      } else {
        sliderCheck(true);
      }
    }
  };

  // slider validate check
  const sliderCheck = useCallback((bool) => {
    setSliderIsValidate(bool);
  }, []);

  const modelTypeHandler = (type, multiGpuMode) => {
    if (type === 0) {
      // gpu일때
      if (gpuModelType === 0) {
        sliderCheck(true);
      } else {
        resourceTypeHandler(type, 1);
      }
    } else if (type === 1) {
      // cpu일때
      if (cpuModelType === 0) {
        sliderCheck(true);
      } else {
        resourceTypeHandler(type, 1);
      }
    }
    setModelType(type);
  };

  const setGpuModelState = (result) => {
    const {
      resourceInfo,
      gpuModel,
      gpuCount: gpuUsage,
      enableCpu,
      enableGpu,
    } = result;

    setMaxGpuUsageCountForRandom(resourceInfo?.gpu_usage_status?.free_gpu);
    setGpuTotalCountForRandom(resourceInfo?.gpu_usage_status?.total_gpu);
    const gpuModelStatus = resourceInfo?.gpu_model_status;
    let gpuModelListOptions = gpuModelStatus.map((v) => ({
      ...v,
      selected: false,
      node_list: v.node_list.map((n) => ({
        ...n,
        selected: false,
      })),
    }));

    // gpu model 선택 넣기
    const gpuModelObj = gpuModel ? gpuModel : {};
    gpuModelListOptions = gpuModelListOptions.map((v) => {
      return {
        ...v,
        selected: Object.keys(gpuModelObj).indexOf(v.model) !== -1,
        node_list: v.node_list.map((n) => ({
          ...n,
          selected: gpuModelObj[n.model]
            ? gpuModelObj[n.model].indexOf(n.name) !== -1
            : false,
        })),
      };
    });

    gpuModelListOptions.map(({ node_list: nodeList }, idx) => {
      cpuModelList[idx] = nodeList.filter(({ selected }) => selected);
      return cpuModelList;
    });

    setCpuModelList(cpuModelList);
    const gpuModelList = gpuModelListOptions.filter(({ selected }) => selected);
    const gpuState = gpuModelState(gpuModelListOptions, gpuModelList, gpuUsage);

    setGpuModelListOptions(gpuState.gpuModelListOptions);
    setGpuModelList(gpuState.gpuModelList);
    setIsMigModel(gpuState.isMigModel);
    setMaxGpuUsageCount(gpuState.maxGpuUsageCount);
    setGpuTotalCount(gpuState.gpuTotalCount);
    setGpuUsage(gpuState.gpuUsage);
    setGpuUsageError(gpuState.gpuUsageError);

    // GPU, CPU 사용 불가능한 빌트인모델에 대해서 최대/최소 GPU 개수 적용
    if (enableGpu === 0) {
      setGpuUsage(0);
      setGpuUsageError('');
      setMinGpuUsage(0);
      setMaxGpuUsage(0);
    } else if (enableCpu === 0) {
      setMinGpuUsage(1);
      setMaxGpuUsage(10000);
    } else {
      setMinGpuUsage(0);
      setGpuUsage(gpuUsage);
      setMaxGpuUsage(10000);
    }
  };

  // GPU 타입 이벤트 핸들러
  const gpuModelTypeHandler = (value) => {
    setGpuModelType(parseInt(value, 10));
    if (!gpuModelList || gpuModelList.length === 0) {
      setGpuUsageError(null);
    } else if (isMigModel) {
      setGpuUsage(1);
      setGpuUsageError('');
    }

    // gpu일때
    if (value === 0) {
      sliderCheck(true);
    } else {
      resourceTypeHandler(0, value);
    }
  };

  const submitBtnHandler = () => {
    const node_name_cpu = {};
    const node_name_gpu = {};
    if (modelType === 1) {
      if (cpuModelType === 1) {
        sliderData?.cpu_model_status?.forEach((v, i) => {
          v.node_list?.forEach((node, idx) => {
            if (detailSelectedOptions[i][i][idx]) {
              //*  Check 여부 판단
              const sliderCpuValue = Object.values(cpuDetailValue[i]);
              const sliderRamValue = Object.values(ramDetailValue[i]);
              Object.assign(node_name_cpu, {
                [node?.node_name]: {
                  cpu_cores_limit_per_pod: sliderCpuValue[idx],
                  ram_limit_per_pod: sliderRamValue[idx],
                },
              });
            }
          });
        });
        Object.assign(node_name_cpu, {
          '@all': {
            is_active: cpuSliderMove,
            // detail과 같은 key로 total값 넣는다.
            cpu_cores_limit_per_pod: cpuTotalValue,
            ram_limit_per_pod: ramTotalValue,
          },
        });
      }
    } else {
      sliderData?.gpu_model_status?.forEach((v, i) => {
        v.node_list?.forEach((node, idx) => {
          if (gpuDetailSelectedOptions[i][i][idx]) {
            // Check 여부 판단
            const sliderGpuValue = Object.values(gpuDetailValue[i]);
            const sliderRamValue = Object.values(gpuRamDetailValue[i]);

            Object.assign(node_name_gpu, {
              [node?.name]: {
                cpu_cores_limit_per_gpu: sliderGpuValue[idx],
                ram_limit_per_gpu: sliderRamValue[idx],
              },
            });
          }
        });
      });
      const gpuAllData = {
        '@all': {
          is_active: gpuTotalSliderMove,
          cpu_cores_limit_per_gpu: gpuTotalValue,
          ram_limit_per_gpu: gpuRamTotalValue,
        },
      };

      Object.assign(node_name_gpu, gpuAllData);
    }

    return { node_name_gpu, node_name_cpu };
  };

  // CPU 타입 이벤트 핸들러
  const cpuModelTypeHandler = (value) => {
    setCpuModelType(Number(value));
    if (value === 0) {
      sliderCheck(true);
    } else {
      resourceTypeHandler(1, value);
    }
  };

  // CheckboxHandler
  const checkboxHandler = ({ idx, status, cpuIdx, type }) => {
    const isTrue = (el) => {
      if (el) return true;
    };
    const trueCheckHandler = (checkbox = []) => {
      if (checkbox.length > 0) {
        const checkTrue = checkbox.filter((check) => check);
        return checkTrue.length > 0;
      }
    };
    if (type === 'cpu') {
      const cpuDetail = _.cloneDeep(cpuDetailValue);
      const cpuRamDetail = _.cloneDeep(ramDetailValue);

      if (status === 'all') {
        // 전체 체크 클릭 시
        const newCpuDetail = {};
        const newCpuRamDetail = {};
        // 체크박스 클릭했을 때 제한 수 확인하고 totalvalue 할당
        if (sliderData?.cpu_model_status?.length > 0) {
          sliderData.cpu_model_status[idx]?.node_list.forEach((v, i) => {
            const cpuMaxValue = v?.resource_info?.cpu_cores_limit_per_pod;

            if (cpuMaxValue < cpuTotalValue) {
              newCpuDetail[i] = cpuMaxValue;
            } else {
              newCpuDetail[i] = cpuTotalValue;
            }

            const ramMaxValue = v?.resource_info?.ram_limit_per_pod;
            if (ramMaxValue < ramTotalValue) {
              newCpuRamDetail[i] = ramMaxValue;
            } else {
              newCpuRamDetail[i] = ramTotalValue;
            }
          });
        }

        cpuDetail[idx] = newCpuDetail;
        cpuRamDetail[idx] = newCpuRamDetail;

        setCpuDetailValue(cpuDetail);
        setRamDetailValue(cpuRamDetail);

        const prevSelectedOptions = cpuSelectedOptions.slice(0, idx);
        const currSelectedOptions = {
          [idx]: !Object.values(cpuSelectedOptions[idx])[0],
        };
        const nextSelectedOptions = cpuSelectedOptions.slice(
          idx + 1,
          cpuSelectedOptions.length,
        );
        const newSelectedOptions = [
          ...prevSelectedOptions,
          currSelectedOptions,
          ...nextSelectedOptions,
        ];

        setCpuSelectedOptions(newSelectedOptions);

        const [allCheck] = Object.values(currSelectedOptions);

        let [arrayLength] = Object.values(detailSelectedOptions[idx]);
        let newDetailValues = [];
        if (allCheck) {
          // 전체 선택 체크
          newDetailValues = Array(arrayLength?.length).fill(true);
          sliderCheck(true);
        } else {
          // 전체 선택 해제
          newDetailValues = Array(arrayLength?.length).fill(false);

          sliderCheck(false);
        }
        const newDetailOptions = [];
        detailSelectedOptions.forEach((value, index) => {
          if (index === idx) {
            newDetailOptions.push({ [idx]: newDetailValues });
          } else {
            newDetailOptions.push(value);
          }
        });
        setDetailSelectedOptions(newDetailOptions);

        let noCheck = true;
        newDetailOptions?.forEach((el) => {
          const [detailChecked] = Object.values(el);

          const check = trueCheckHandler(detailChecked);

          if (check) {
            noCheck = false;
            sliderCheck(true);
          }
        });

        if (noCheck) {
          sliderCheck(false);
        }
      } else if (status === 'detail') {
        // cpu 모델 특정 - detail
        // 체크박스 클릭했을 때 제한 수 확인하고 totalvalue 할당
        let cpuDetailValue =
          sliderData.cpu_model_status[cpuIdx]?.node_list[idx]?.resource_info
            .cpu_cores_limit_per_gpu;
        if (cpuDetailValue > cpuTotalValue) {
          cpuDetailValue = cpuTotalValue;
        }
        let cpuRamDetailValue =
          sliderData.cpu_model_status[cpuIdx]?.node_list[idx]?.resource_info
            .ram_limit_per_gpu;

        if (cpuRamDetailValue > ramTotalValue) {
          cpuRamDetailValue = ramTotalValue;
        }
        cpuDetail[cpuIdx][idx] = cpuDetailValue;
        cpuRamDetail[cpuIdx][idx] = cpuRamDetailValue;
        setCpuDetailValue(cpuDetail);
        setRamDetailValue(cpuRamDetail);

        const [copiedDetailValues] = Object.values(
          detailSelectedOptions[cpuIdx],
        ).slice();

        const copiedDetailObject = detailSelectedOptions.slice();
        const prevDetailObject = copiedDetailObject.slice(0, cpuIdx);
        const nextDetailObject = copiedDetailObject.slice(
          cpuIdx + 1,
          copiedDetailObject.length,
        );
        const prevSelectedValue = copiedDetailValues.slice(0, idx);
        const currSelectedValue = !copiedDetailValues[idx];
        const nextSelectedValue = copiedDetailValues.slice(
          idx + 1,
          copiedDetailValues.length,
        );

        const detailArrayValues = [
          ...prevSelectedValue,
          currSelectedValue,
          ...nextSelectedValue,
        ];

        const currDetailObject = {
          [cpuIdx]: detailArrayValues,
        };

        const newDetailSelectedValues = [
          ...prevDetailObject,
          currDetailObject,
          ...nextDetailObject,
        ];

        setDetailSelectedOptions(newDetailSelectedValues);
        const [valueCheck] = detailArrayValues.filter(isTrue);

        if (valueCheck) {
          sliderCheck(true);
          const newCpuSelectedOptions = [];
          cpuSelectedOptions.forEach((option, idx) => {
            if (idx === cpuIdx) {
              newCpuSelectedOptions.push({ [cpuIdx]: true });
            } else {
              newCpuSelectedOptions.push(option);
            }
          });
          setCpuSelectedOptions(newCpuSelectedOptions);
          // btcnCheck
        } else {
          const newCpuSelectedOptions = [];
          cpuSelectedOptions.forEach((option, idx) => {
            if (idx === cpuIdx) {
              newCpuSelectedOptions.push({ [cpuIdx]: false });
            } else {
              newCpuSelectedOptions.push(option);
            }
          });
          setCpuSelectedOptions(newCpuSelectedOptions);
          // btcnCheck
          const isTrue = (checkbox = []) => {
            if (checkbox.length > 0) {
              const checkTrue = checkbox.filter((check) => check);
              return checkTrue.length > 0;
            }
          };
          newCpuSelectedOptions?.forEach((el) => {
            const check = isTrue(Object.values(el));
            if (check) {
              // 체크크
              sliderCheck(true);
            } else {
              sliderCheck(false);
            }
          });
        }
      }
    } else if (type === 'gpu') {
      // 새로운 gpu 로직
      const gpuDetail = _.cloneDeep(gpuDetailValue);
      const gpuRamDetail = _.cloneDeep(gpuRamDetailValue);

      if (status === 'all') {
        const newGpuDetail = {};
        const newGpuRamDetail = {};
        // 체크박스 클릭했을 때 제한 수 확인하고 totalvalue 할당

        if (sliderData?.gpu_model_status?.length > 0) {
          sliderData.gpu_model_status[idx]?.node_list.forEach((v, i) => {
            const gpuMaxValue = v?.resource_info?.cpu_cores_limit_per_gpu;
            if (gpuMaxValue < gpuTotalValue) {
              newGpuDetail[i] = gpuMaxValue;
            } else {
              newGpuDetail[i] = gpuTotalValue;
            }

            const ramMaxValue = v?.resource_info?.ram_limit_per_gpu;
            if (ramMaxValue < gpuRamTotalValue) {
              newGpuRamDetail[i] = ramMaxValue;
            } else {
              newGpuRamDetail[i] = gpuRamTotalValue;
            }
          });
        }

        gpuDetail[idx] = newGpuDetail;
        gpuRamDetail[idx] = newGpuRamDetail;

        setGpuDetailValue(gpuDetail);
        setGpuRamDetailValue(gpuRamDetail);

        const prevSelectedOptions = gpuSelectedOptions.slice(0, idx);
        const currSelectedOptions = {
          [idx]: !Object.values(gpuSelectedOptions[idx])[0],
        };
        const nextSelectedOptions = gpuSelectedOptions.slice(
          idx + 1,
          gpuSelectedOptions.length,
        );
        const newSelectedOptions = [
          ...prevSelectedOptions,
          currSelectedOptions,
          ...nextSelectedOptions,
        ];
        setGpuSelectedOptions(newSelectedOptions);

        const [allCheck] = Object.values(currSelectedOptions);

        let [arrayLength] = Object.values(gpuDetailSelectedOptions[idx]);

        let newDetailValues = [];
        if (allCheck) {
          // 전체 선택 체크

          newDetailValues = Array(arrayLength?.length).fill(true);
          sliderCheck(true);
        } else {
          // 전체 선택 해제
          newDetailValues = Array(arrayLength?.length).fill(false);
        }
        // 0이 들어오면
        const newDetailOptions = [];
        gpuDetailSelectedOptions.forEach((value, index) => {
          if (index === idx) {
            newDetailOptions.push({ [idx]: newDetailValues });
          } else {
            newDetailOptions.push(value);
          }
        });
        setGpuDetailSelectedOptions(newDetailOptions);
        let noCheck = true;
        newDetailOptions?.forEach((el) => {
          const [detailChecked] = Object.values(el);

          const check = trueCheckHandler(detailChecked);

          if (check) {
            noCheck = false;
            sliderCheck(true);
          }
        });

        if (noCheck) {
          sliderCheck(false);
        }
      } else if (status === 'detail') {
        // 체크박스 클릭했을 때 제한 수 확인하고 totalvalue 할당
        let gpuDetailValue =
          sliderData.gpu_model_status[cpuIdx]?.node_list[idx]?.resource_info
            .cpu_cores_limit_per_gpu;
        if (gpuDetailValue > gpuTotalValue) {
          gpuDetailValue = gpuTotalValue;
        }
        let gpuRamDetailValue =
          sliderData.gpu_model_status[cpuIdx]?.node_list[idx]?.resource_info
            .ram_limit_per_gpu;

        if (gpuRamDetailValue > gpuRamTotalValue) {
          gpuRamDetailValue = gpuRamTotalValue;
        }
        gpuDetail[cpuIdx][idx] = gpuDetailValue;
        gpuRamDetail[cpuIdx][idx] = gpuRamDetailValue;

        const [copiedDetailValues] = Object.values(
          gpuDetailSelectedOptions[cpuIdx],
        ).slice();
        const copiedDetailObject = gpuDetailSelectedOptions.slice();
        const prevDetailObject = copiedDetailObject.slice(0, cpuIdx);
        const nextDetailObject = copiedDetailObject.slice(
          cpuIdx + 1,
          copiedDetailObject.length,
        );
        const prevSelectedValue = copiedDetailValues.slice(0, idx);
        const currSelectedValue = !copiedDetailValues[idx];
        const nextSelectedValue = copiedDetailValues.slice(
          idx + 1,
          copiedDetailValues.length,
        );

        const detailArrayValues = [
          ...prevSelectedValue,
          currSelectedValue,
          ...nextSelectedValue,
        ];

        const currDetailObject = {
          [cpuIdx]: detailArrayValues,
        };

        const newDetailSelectedValues = [
          ...prevDetailObject,
          currDetailObject,
          ...nextDetailObject,
        ];
        setGpuDetailSelectedOptions(newDetailSelectedValues);

        const [valueCheck] = detailArrayValues.filter(isTrue);

        let noCheck = true;
        newDetailSelectedValues?.forEach((el) => {
          const [detailChecked] = Object.values(el);

          const check = trueCheckHandler(detailChecked);

          if (check) {
            noCheck = false;
            sliderCheck(true);
          }
        });
        if (noCheck) {
          sliderCheck(false);
        }
        if (valueCheck) {
          const newGpuSelectedOptions = [];

          gpuSelectedOptions.forEach((option, idx) => {
            if (idx === cpuIdx) {
              newGpuSelectedOptions.push({ [cpuIdx]: true });
            } else {
              newGpuSelectedOptions.push(option);
            }
          });
          setGpuSelectedOptions(newGpuSelectedOptions);
        } else {
          const newGpuSelectedOptions = [];
          gpuSelectedOptions.forEach((option, idx) => {
            if (idx === cpuIdx) {
              newGpuSelectedOptions.push({ [cpuIdx]: false });
            } else {
              newGpuSelectedOptions.push(option);
            }
          });
          setGpuSelectedOptions(newGpuSelectedOptions);
        }
        setGpuDetailValue(gpuDetail);
        setGpuRamDetailValue(gpuRamDetail);
      }
    }
  };

  // 넘버 인풋 이벤트 핸들러
  const gpuUsageHandler = (e) => {
    let { value, min, max } = e;
    let validate = null;

    if (value === '') {
      validate = 'gpuUsage.empty.message';
    } else {
      if (parseInt(value) < parseInt(min)) {
        value = min;
      }
      if (parseInt(value) > parseInt(max)) {
        value = max;
      }
      validate = '';
    }
    setGpuUsage(value);
    setGpuUsageError(validate);
  };

  const detailGpuValueHandler = (idx, id, value, option) => {
    // detial slider value 조정할 때 실행하는 함수
    if (value === 0 || value < 0) {
      value = 1;
    }
    setGpuTotalSliderMove(false);
    if (option === 'gpu') {
      const copiedDetailValue = JSON.parse(JSON.stringify(gpuDetailValue));
      const nodeName = sliderData.gpu_model_status[idx]?.node_list[id]?.name;

      sliderData.gpu_model_status.forEach((v, i) => {
        v.node_list.forEach((node, index) => {
          if (node.name === nodeName) {
            copiedDetailValue[i][index] = value;
          }
        });
      });

      setGpuDetailValue(copiedDetailValue);
    } else if (option === 'ram') {
      const copiedDetailValue = JSON.parse(JSON.stringify(gpuRamDetailValue));
      copiedDetailValue[idx][id] = value;
      setGpuRamDetailValue(copiedDetailValue);
    }
  };

  const detailCpuValueHandler = (idx, id, value, option) => {
    if (value === 0 || value < 0) {
      value = 1;
    }
    setCpuSliderMove(false);

    if (option === 'cpu') {
      const copiedDetailValue = JSON.parse(JSON.stringify(cpuDetailValue));
      copiedDetailValue[idx][id] = value;

      setCpuDetailValue(copiedDetailValue);
    } else if (option === 'ram') {
      const copiedDetailValue = JSON.parse(JSON.stringify(ramDetailValue));
      copiedDetailValue[idx][id] = value;
      setRamDetailValue(copiedDetailValue);
    }
  };

  const totalSliderHandler = (type) => {
    // total false로 바꾸는 함수
    if (type === 'cpu') {
      setCpuSliderMove(false);
    } else if (type === 'gpu') {
      setGpuTotalSliderMove(false);
    }
  };

  const totalValueChange = (v, option, type) => {
    // 전체 슬라이더 조정
    if (v === 0 || v < 0) {
      v = 1;
    }
    if (type === 'cpu') {
      setCpuSliderMove(true);
    }
    if (type === 'gpu') {
      setGpuTotalSliderMove(true);
    }
    let nodeObj = {};
    const newObj = {};

    if (sliderData?.cpu_model_status?.length > 0 && type === 'cpu') {
      sliderData?.cpu_model_status?.forEach(({ node_list: nodeList }, idx) => {
        nodeObj = {};
        if (nodeList?.length > 0) {
          nodeList.forEach((value, i) => {
            if (option === 'cpu') {
              const cpuMaxValue = value?.resource_info?.cpu_cores_limit_per_pod;

              if (cpuMaxValue < v) {
                nodeObj[i] = cpuMaxValue;
              } else {
                nodeObj[i] = v;
              }
            } else if (option === 'ram') {
              const ramMaxValue = value?.resource_info?.ram_limit_per_pod;
              if (ramMaxValue < v) {
                nodeObj[i] = ramMaxValue;
              } else {
                nodeObj[i] = v;
              }
            }
          });
          newObj[idx] = nodeObj;
        }
      });
      if (option === 'cpu') {
        setCpuDetailValue(newObj);
      } else if (option === 'ram') {
        setRamDetailValue(newObj);
      }
    }
    if (sliderData?.gpu_model_status?.length > 0 && type === 'gpu') {
      sliderData?.gpu_model_status?.forEach(({ node_list: nodeList }, idx) => {
        nodeObj = {};
        if (nodeList?.length > 0) {
          nodeList.forEach((value, i) => {
            if (option === 'gpu') {
              const gpuMaxValue = value?.resource_info?.cpu_cores_limit_per_gpu;

              if (gpuMaxValue < v) {
                nodeObj[i] = gpuMaxValue;
              } else {
                nodeObj[i] = v;
              }
            } else if (option === 'ram') {
              const ramMaxValue = value?.resource_info?.ram_limit_per_gpu;

              if (ramMaxValue < v) {
                nodeObj[i] = ramMaxValue;
              } else {
                nodeObj[i] = v;
              }
            }
          });
          newObj[idx] = nodeObj;
        }
      });
      if (option === 'gpu') {
        setGpuDetailValue(newObj);
      } else if (option === 'ram') {
        setGpuRamDetailValue(newObj);
      }
    }
  };

  const totalValueHandler = (v, option, type) => {
    if (v === 0 || v < 0) {
      v = 1;
    }

    if (type === 'cpu') {
      if (option === 'cpu') {
        setCpuTotalValue(v);
        setCpuSliderMove(true);
      } else if (option === 'ram') {
        setRamTotalValue(v);
        setCpuSliderMove(true);
      }
    } else if (type === 'gpu') {
      if (option === 'gpu') {
        setGpuTotalValue(v);
        setGpuTotalSliderMove(true);
      } else if (option === 'ram') {
        setGpuRamTotalValue(v);
        setGpuTotalSliderMove(true);
      }
    }
    totalValueChange(v, option, type);
  };

  // GPU 모델 선택 이벤트 핸들러
  const gpuSelectHandler = (type, idx, nodeIdx) => {
    const copiedGpuModelListOptions = JSON.parse(
      JSON.stringify(gpuModelListOptions),
    );
    let cpuModelListOptions = gpuModelListOptions[idx].node_list;
    if (type === 'gpu') {
      gpuModelListOptions[idx].selected = !gpuModelListOptions[idx].selected;
      // GPU 모델 선택/선택해제시 CPU 모델 전체 선택/선택해제
      cpuModelListOptions = cpuModelListOptions.map((v) => {
        return {
          ...v,
          selected: gpuModelListOptions[idx].selected,
        };
      });
      gpuModelListOptions[idx].node_list = cpuModelListOptions;
      setGpuModelListOptions(gpuModelListOptions);
    } else {
      cpuModelListOptions[nodeIdx].selected =
        !cpuModelListOptions[nodeIdx].selected;
      copiedGpuModelListOptions[idx].node_list = cpuModelListOptions;
      if (!copiedGpuModelListOptions[idx].selected) {
        // GPU 선택 안되어 있을 경우 선택
        copiedGpuModelListOptions[idx].selected = true;
      }
      if (!cpuModelListOptions[nodeIdx].selected) {
        // CPU 선택 해제하는 경우 CPU 선택 개수 0이면 GPU 선택도 해제
        if (
          cpuModelListOptions.filter(({ selected }) => selected).length === 0
        ) {
          copiedGpuModelListOptions[idx].selected = false;
        }
      }
    }
    let newCpuModelList = [...cpuModelList];
    newCpuModelList[idx] = cpuModelListOptions.filter(
      ({ selected }) => selected,
    );
    const gpuModelList = gpuModelListOptions.filter(({ selected }) => selected);
    const {
      //gpuModelListOptions: resourceOptions,
      gpuModelList: selectedResource,
      isMigModel,
      maxGpuUsageCount,
      gpuTotalCount,
      gpuUsage: gpuCount,
      gpuUsageError: gpuCountError,
    } = gpuModelState(
      copiedGpuModelListOptions,
      gpuModelList,
      gpuUsage,
      gpuUsageError,
    );

    setCpuModelList(newCpuModelList);
    setGpuModelList(selectedResource);
    setIsMigModel(isMigModel);
    setMaxGpuUsageCount(maxGpuUsageCount);
    setGpuTotalCount(gpuTotalCount);
    setGpuUsage(gpuCount);
    setGpuUsageError(gpuCountError);
  };

  const makeResultJson = (cpuModelList) => {
    // 선택 변경 됐을 때 gpuModel 결과 포맷으로 변환하여 저장
    let gpuModelNodeListJson = {};
    cpuModelList.map((v) => {
      if (v.length > 0) {
        v.map(({ name, model }, idx) => {
          if (idx === 0) {
            gpuModelNodeListJson[model] = [name];
          } else {
            gpuModelNodeListJson[model].push(name);
          }
          return gpuModelNodeListJson[model];
        });
      }
      return gpuModelNodeListJson;
    });
    return gpuModelNodeListJson;
  };

  const sliderSwitchHandler = (type) => {
    if (type === 'cpu') {
      setCpuSwitchStatus(!cpuSwitchStatus);
      setCpuSliderMove(cpuSwitchStatus);
      if (cpuSwitchStatus) {
        totalValueChange(ramTotalValue, 'ram', type);
        totalValueChange(cpuTotalValue, 'cpu', type);
      }
    } else if (type === 'gpu') {
      if (gpuSwitchStatus) {
        totalValueChange(gpuRamTotalValue, 'ram', type);
        totalValueChange(gpuTotalValue, 'gpu', type);
      }

      setGpuTotalSliderMove(gpuSwitchStatus);
      setGpuSwitchStatus(!gpuSwitchStatus);
    }
  };

  useEffect(() => {
    const cpuStateHandler = () => {
      if (sliderData?.cpu_model_status?.length > 0) {
        const selectedOptions = [];
        const detailSelectedOption = [];
        let selectedItemBucket = [];
        let nodeCpuObj = {};
        let nodeRamObj = {};
        const cpuObj = {};
        const ramObj = {};
        let cpuPerPod = 1;
        let ramPerPod = 1;
        sliderData?.cpu_model_status.forEach(({ node_list: nodeList }, idx) => {
          nodeCpuObj = {};
          nodeRamObj = {};
          selectedItemBucket = [];
          selectedOptions.push({ [idx]: false });
          if (nodeList?.length > 0) {
            nodeList.forEach(({ resource_info }) => {
              const {
                cpu_cores_limit_per_pod: cpuPod,
                ram_limit_per_pod: ramPod,
              } = resource_info;

              if (cpuPerPod < cpuPod) {
                cpuPerPod = cpuPod;
              }

              if (ramPerPod < ramPod) {
                ramPerPod = ramPod;
              }
            });

            setCpuAndRamSliderValue({ cpu: cpuPerPod, ram: ramPerPod });
            let isActive = false;
            nodeList.forEach((v, i) => {
              let selectedItemValue = false;
              let prevCpuValue = 1;
              let prevRamValue = 1;
              if (type === 'EDIT_TRAINING_TOOL') {
                const prevCpu = Object.keys(prevSliderData.node_name_cpu);
                if (gpuCount === 0) {
                  setModelType(1);
                  if (prevCpu.length < 1) {
                    setCpuModelType(0);
                  }
                }
                if (prevCpu.length > 0 && prevSliderData.node_name_cpu_all) {
                  setCpuModelType(1);

                  if (prevSliderData.node_name_cpu_all.is_active) {
                    prevCpuValue =
                      prevSliderData.node_name_cpu_all.cpu_cores_limit_per_pod;
                    prevRamValue =
                      prevSliderData.node_name_cpu_all.ram_limit_per_pod;
                    isActive = true;
                    setCpuSwitchStatus(false);
                    setCpuSliderMove(true);
                  } else if (
                    prevSliderData.node_name_cpu_all.is_active === false
                  ) {
                    setCpuSwitchStatus(true);
                  }

                  prevCpu.forEach((nodeName) => {
                    if (nodeName === v.node_name) {
                      selectedOptions[idx][idx] = true;
                      const { cpu_cores_limit_per_pod, ram_limit_per_pod } =
                        prevSliderData.node_name_cpu[nodeName];

                      const prevMaxGpuValue =
                        prevCpuValue > cpu_cores_limit_per_pod
                          ? cpu_cores_limit_per_pod
                          : prevCpuValue;
                      const prevMaxRamValue =
                        prevRamValue > ram_limit_per_pod
                          ? ram_limit_per_pod
                          : prevRamValue;

                      nodeCpuObj[i] = isActive
                        ? prevMaxGpuValue
                        : cpu_cores_limit_per_pod; // 일단 20인데 그 안에 prevValue를 넣어야함
                      nodeRamObj[i] = isActive
                        ? prevMaxRamValue
                        : ram_limit_per_pod;
                      sliderCheck(true);
                      selectedItemValue = true;
                    } else {
                      if (!nodeCpuObj[i] && !nodeRamObj[i]) {
                        nodeCpuObj[i] = 1;
                        nodeRamObj[i] = 1;
                      }
                    }
                  });
                } else {
                  nodeCpuObj[i] = 1;
                  nodeRamObj[i] = 1;
                  selectedItemValue = false;
                  sliderCheck(true);
                }
              } else {
                nodeCpuObj[i] = 1;
                nodeRamObj[i] = 1;
                selectedItemValue = false;
              }
              selectedItemBucket.push(selectedItemValue);
            });
            detailSelectedOption.push({ [idx]: selectedItemBucket });
            cpuObj[idx] = nodeCpuObj;
            ramObj[idx] = nodeRamObj;
          }
        });

        setCpuDetailValue(cpuObj);
        setRamDetailValue(ramObj);
        setCpuSelectedOptions(selectedOptions);
        setDetailSelectedOptions(detailSelectedOption);
      }
    };

    const gpuStateHandler = () => {
      // gpu 기본 state 깔기
      if (sliderData?.gpu_model_status?.length > 0) {
        let selectedOptions = [];
        let detailSelectedOption = [];
        let selectedItemBucket = [];
        let nodeGpuObj = {};
        let nodeRamObj = {};
        const gpuObj = {};
        const ramObj = {};
        let gpuPerPod = 1;
        let ramPerPod = 1;

        sliderData?.gpu_model_status.forEach(
          ({ node_list: nodeList, model }, idx) => {
            nodeGpuObj = {};
            nodeRamObj = {};
            selectedItemBucket = [];
            selectedOptions.push({ [idx]: false });
            if (nodeList?.length > 0) {
              nodeList.forEach(({ resource_info }) => {
                const {
                  cpu_cores_limit_per_gpu: gpuPod,
                  ram_limit_per_gpu: ramPod,
                } = resource_info;
                if (gpuPerPod < gpuPod) {
                  gpuPerPod = gpuPod;
                }
                if (ramPerPod < ramPod) {
                  ramPerPod = ramPod;
                }
              });
              setGpuAndRamSliderValue({ cpu: gpuPerPod, ram: ramPerPod });
              let isActive = false;

              nodeList.forEach((v, i) => {
                let selectedItemValue = false;
                let prevGpuValue = 1;
                let prevRamValue = 1;

                if (type === 'EDIT_TRAINING_TOOL') {
                  // * EDIT

                  let prevSelectedGpuModels = [];

                  if (gpuModels) {
                    prevSelectedGpuModels = Object.keys(gpuModels);
                  }
                  const prevSelectedGpuModelCheck =
                    prevSelectedGpuModels.indexOf(model);
                  const prevGpu = Object.keys(prevSliderData.node_name_gpu);
                  if (prevGpu.length > 0 && prevSliderData.node_name_gpu_all) {
                    setModelType(0);
                    if (prevSelectedGpuModels.length > 0) {
                      setGpuModelType(1);
                    } else {
                      sliderCheck(true);
                      setGpuSwitchStatus(false);
                    }

                    if (prevSliderData.node_name_gpu_all.is_active) {
                      prevGpuValue =
                        prevSliderData.node_name_gpu_all
                          .cpu_cores_limit_per_gpu;
                      prevRamValue =
                        prevSliderData.node_name_gpu_all.ram_limit_per_gpu;
                      isActive = true;
                      setGpuTotalSliderMove(true);
                      setGpuSwitchStatus(false);
                    } else if (
                      prevSliderData.node_name_gpu_all.is_active === false
                    ) {
                      setGpuSwitchStatus(true);
                    }

                    prevGpu.forEach((nodeName) => {
                      if (
                        nodeName === v.name &&
                        prevSelectedGpuModelCheck !== -1
                      ) {
                        selectedOptions[idx][idx] = true;
                        const { cpu_cores_limit_per_gpu, ram_limit_per_gpu } =
                          prevSliderData.node_name_gpu[nodeName];

                        const prevMaxGpuValue =
                          prevGpuValue > cpu_cores_limit_per_gpu
                            ? cpu_cores_limit_per_gpu
                            : prevGpuValue;
                        const prevMaxRamValue =
                          prevRamValue > ram_limit_per_gpu
                            ? ram_limit_per_gpu
                            : prevRamValue;
                        nodeGpuObj[i] = isActive
                          ? prevMaxGpuValue
                          : cpu_cores_limit_per_gpu;
                        nodeRamObj[i] = isActive
                          ? prevMaxRamValue
                          : ram_limit_per_gpu;
                        if (modelType === 0) {
                          sliderCheck(true);
                        }
                        selectedItemValue = true;
                      } else {
                        if (!nodeGpuObj[i] && !nodeRamObj[i]) {
                          nodeGpuObj[i] = 1;
                          nodeRamObj[i] = 1;
                        }
                      }
                    });
                  } else {
                    nodeGpuObj[i] = 1;
                    nodeRamObj[i] = 1;
                    selectedItemValue = false;
                    sliderCheck(true);
                  }
                } else {
                  nodeGpuObj[i] = 1;
                  nodeRamObj[i] = 1;
                  selectedItemValue = false;
                }
                selectedItemBucket.push(selectedItemValue);
              });
              detailSelectedOption.push({ [idx]: selectedItemBucket });
              gpuObj[idx] = nodeGpuObj;

              ramObj[idx] = nodeRamObj;
            }
          },
        );

        setGpuDetailValue(gpuObj);
        setGpuRamDetailValue(ramObj);
        setGpuSelectedOptions(selectedOptions);
        setGpuDetailSelectedOptions(detailSelectedOption);
      }
    };

    if (isMount.current) {
      if (type === 'EDIT_TRAINING_TOOL') {
        if (sliderData && prevSliderData && gpuModels) {
          isMount.current = false;
          cpuStateHandler();
          gpuStateHandler();
        }
      } else {
        if (sliderData) {
          isMount.current = false;
          sliderCheck(true);
          cpuStateHandler();
          gpuStateHandler();
        }
      }
    }
  }, [
    sliderData,
    prevSliderData,
    type,
    modelType,
    sliderCheck,
    gpuModels,
    gpuCount,
  ]);

  useEffect(() => {
    // slider edit - 초깃값 변경
    if (prevSliderData) {
      const prevGpuTotalValue =
        prevSliderData?.node_name_gpu_all?.cpu_cores_limit_per_gpu;
      const prevCpuTotalValue =
        prevSliderData?.node_name_cpu_all?.cpu_cores_limit_per_pod;

      const prevRamTotalValue =
        prevSliderData?.node_name_cpu_all?.ram_limit_per_pod;

      const prevGpuRamTotalValue =
        prevSliderData?.node_name_gpu_all?.ram_limit_per_gpu;
      setGpuTotalValue(
        typeof prevGpuTotalValue === 'number' ? prevGpuTotalValue : 1,
      );
      setCpuTotalValue(
        typeof prevCpuTotalValue === 'number' ? prevCpuTotalValue : 1,
      );
      setRamTotalValue(
        typeof prevRamTotalValue === 'number' ? prevRamTotalValue : 1,
      );
      setGpuRamTotalValue(
        typeof prevGpuRamTotalValue === 'number' ? prevGpuRamTotalValue : 1,
      );
    }
  }, [
    prevSliderData,
    prevSliderData?.node_name_gpu_all?.ram_limit_per_cpu,
    prevSliderData?.node_name_gpu_all?.ram_limit_per_gpu,
  ]);

  function renderSettingBox() {
    return (
      <ResourceSettingBox
        gpuModelType={gpuModelType}
        gpuTotalCount={gpuTotalCount}
        maxGpuUsageCount={maxGpuUsageCount}
        gpuTotalCountForRandom={gpuTotalCountForRandom}
        maxGpuUsageCountForRandom={gpuTotalCountForRandom}
        minGpuUsage={minGpuUsage}
        maxGpuUsage={maxGpuUsage}
        isMigModel={isMigModel}
        gpuModelListOptions={gpuModelListOptions}
        gpuModelList={gpuModelList}
        cpuModelList={cpuModelList}
        gpuUsage={gpuUsage}
        gpuUsageError={gpuUsageError}
        gpuModelTypeHandler={gpuModelTypeHandler}
        gpuSelectHandler={gpuSelectHandler}
        gpuUsageHandler={gpuUsageHandler}
        visualStatus={visualStatus}
        modelTypeHandler={modelTypeHandler}
        modelType={modelType}
        cpuModelTypeHandler={cpuModelTypeHandler}
        cpuModelType={cpuModelType}
        sliderData={sliderData}
        gpuSelectedOptions={gpuSelectedOptions}
        checkboxHandler={checkboxHandler}
        totalValueHandler={totalValueHandler}
        detailGpuValueHandler={detailGpuValueHandler}
        totalSliderHandler={totalSliderHandler}
        sliderSwitchHandler={sliderSwitchHandler}
        detailCpuValueHandler={detailCpuValueHandler}
        gpuTotalValue={gpuTotalValue}
        gpuRamTotalValue={gpuRamTotalValue}
        gpuTotalSliderMove={gpuTotalSliderMove}
        gpuSwitchStatus={gpuSwitchStatus}
        gpuAndRamSliderValue={gpuAndRamSliderValue}
        cpuSwitchStatus={cpuSwitchStatus}
        ramTotalValue={ramTotalValue}
        cpuDetailValue={cpuDetailValue}
        ramDetailValue={ramDetailValue}
        cpuSliderMove={cpuSliderMove}
        cpuAndRamSliderValue={cpuAndRamSliderValue}
        gpuDetailSelectedOptions={gpuDetailSelectedOptions}
        gpuDetailValue={gpuDetailValue}
        gpuRamDetailValue={gpuRamDetailValue}
        submitBtnHandler={submitBtnHandler}
        cpuTotalValue={cpuTotalValue}
        detailSelectedOptions={detailSelectedOptions}
        cpuSelectedOptions={cpuSelectedOptions}
        prevSliderData={prevSliderData}
        sliderIsValidate={sliderIsValidate}
      />
    );
  }

  const result = useMemo(
    () => ({
      gpuModel: gpuModelType === 1 ? makeResultJson(cpuModelList) : null,
      gpuUsage,
      isValid:
        modelType === 0 ? gpuUsage !== '' && gpuUsage !== 0 : sliderIsValidate,
      modelType,
      sliderIsValidate,
    }),
    [gpuModelType, gpuUsage, cpuModelList, modelType, sliderIsValidate],
  );

  return [
    result,
    setGpuModelState,
    renderSettingBox,
    submitBtnHandler,
    modelType,
    sliderIsValidate,
  ];
}

export default useResourceSettingBox;
