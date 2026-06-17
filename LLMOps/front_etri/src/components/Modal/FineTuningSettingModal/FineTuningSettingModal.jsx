import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputNumber } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ResourceSetting from '@src/components/molecules/ResourceSetting';

// Actions
import { closeModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './FineTuningSettingModal.module.scss';

const cx = classNames.bind(style);
function getGpuCalculationResult(
  datasetList,
  gpuSelectedOptions,
  gpuInputValues,
) {
  // 1. gpuSelectedOptions에서 "true"인 객체를 찾는다.
  //    예: [{0:false},{1:false},{2:true}] 중 {2:true}를 찾는다.
  const foundObj = gpuSelectedOptions.find((obj) => {
    // 객체의 value가 true인지 판단
    const values = Object.values(obj);
    return values.length > 0 && values[0] === true;
  });

  // 2. 만약 true를 찾지 못했다면 0을 반환한다. (필요에 따라 예외처리를 달리 해도 됨)
  if (!foundObj) {
    return 0;
  }

  // 3. foundObj가 { 2: true } 라면 key는 "2"이다.
  //    문자열이므로 Number로 변환해서 인덱스로 사용한다.
  const foundIndex = Number(Object.keys(foundObj)[0]);

  // 4. foundIndex가 datasetList와 gpuInputValues 범위를 벗어나는지 체크
  if (
    foundIndex < 0 ||
    foundIndex >= datasetList.length ||
    foundIndex >= gpuInputValues.length
  ) {
    return 0;
  }

  // 5. 곱셈에 사용할 값 가져오기
  const gpuValue = Number(datasetList[foundIndex]?.gpu) || 0;
  const inputValue = Number(gpuInputValues[foundIndex]) || 0;

  // 6. 최종 결과를 반환
  return gpuValue * inputValue;
}

const initialModelData = {
  keyword: '',
  selectedModel: null,
  selectedOption: {
    label: 'total.label',
    value: 'total',
  },
};

const FineTuningSettingModal = ({ data, type }) => {
  const { workspaceId, refresh, modelId, git, onSubmit } = data;
  const { t } = useTranslation();

  const col1 = t('instanceName.label');

  const col2 = <div>{t('totalAmount.label')}</div>;

  const col3 = <div>{t('allocation.label')}</div>;

  const colList = [col1, col2, col3];
  const dispatch = useDispatch();

  const [loadType, setLoadType] = useState(1); // 1 , 0
  const [footerMessage, setFooterMessage] = useState('');

  const [datasetList, setDatasetList] = useState([]);

  const [gpuSelectedOptions, setGpuSelectedOptions] = useState([]);
  const [gpuInputValues, setGpuInputValues] = useState([]);
  const [gpuAllocate, setGpuAllocate] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [validate, setValidate] = useState(false);

  const [modelData, setModelData] = useState({
    modelName: '',
    modelDesc: '',
  });

  const checkboxHandler = ({ idx, flag, initialValue = [] }) => {
    let selectedInstance = [];

    if (gpuSelectedOptions.length === 0) {
      selectedInstance.push(...initialValue);
    } else {
      selectedInstance.push(...gpuSelectedOptions);
    }

    let newFlag = !Object.values(selectedInstance[idx])[0];

    if (typeof flag === 'boolean') {
      newFlag = flag;
    }
    let prevSelectedOptions = selectedInstance.slice(0, idx);
    let currSelectedOptions = {
      [idx]: newFlag,
    };
    let nextSelectedOptions = selectedInstance.slice(
      idx + 1,
      selectedInstance.length,
    );

    const newState = {};

    if (!newFlag) {
      const newGpuInputValues = [...gpuInputValues];
      newGpuInputValues[idx] = '';

      setGpuInputValues(newGpuInputValues);
    } else {
      const newGpuValues = [...gpuInputValues].map((inputVal, index) => '');
      newState.gpuInputValues = newGpuValues;
      setGpuInputValues(newGpuValues);
    }

    const newSelectedOptions = [
      ...prevSelectedOptions,
      currSelectedOptions,
      ...nextSelectedOptions,
    ];

    function updateCheckboxes(arr = [], index) {
      if (
        !Array.isArray(arr) ||
        typeof index !== 'number' ||
        index < 0 ||
        index >= arr.length
      ) {
        throw new Error('Invalid input');
      }

      if (Object.values(arr[index])[0] === true) {
        arr.forEach((obj, i) => {
          if (i !== index) {
            let key = Object.keys(obj)[0];
            obj[key] = false;
          }
        });
      }
      return arr;
    }

    const result = updateCheckboxes(newSelectedOptions, idx);
    setGpuSelectedOptions(result);
  };

  // POST Submit TrainingPage
  const postDatasetFiles = async () => {
    setIsLoading(true);
    const trueIndex = gpuSelectedOptions.findIndex(
      (item) => Object.values(item)[0] === true,
    );
    if (trueIndex !== -1) {
      const id = datasetList[trueIndex].id;
      const gpuInputValue = gpuInputValues[trueIndex];

      const post = await onSubmit({
        instanceId: id,
        instanceCount: gpuInputValue,
        gpuCount: gpuAllocate,
      });
      setIsLoading(false);
      if (post) {
        dispatch(closeModal('FINETUNING_SETTING'));
      }
    }
  };

  // GET 데이터셋
  const getDataset = useCallback(
    async ({ keyword = '' } = {}) => {
      let url = `models/option/instances?workspace_id=${workspaceId}`;

      const response = await callApi({
        url,
        method: 'get',
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        const newData = result.map((item) => ({
          cpu: item.cpu_allocate,
          gpu: item.gpu_allocate,
          total: item.instance_allocate,
          id: item.instance_id,
          gpu_name: item.gpu_allocate !== 0 ? item.instance_name : false,
          ram: item.ram_allocate,
          name:
            item.gpu_allocate === 0 ? item.instance_name : item.resource_name,
        }));

        let selectedOptions = [];

        let selectedItemValue = [];
        const initialInputValues = [];
        if (result?.length > 0) {
          result.forEach(({ records }, idx) => {
            selectedItemValue = [];
            selectedOptions.push({ [idx]: false });
            initialInputValues.push('');
            if (records?.length > 0) {
              records.forEach(() => {
                selectedItemValue.push(false);
              });
            }
          });

          setGpuSelectedOptions(selectedOptions);
          setGpuInputValues(initialInputValues);
        }

        setDatasetList(newData);
      } else {
        errorToastMessage(error, message);
      }
    },
    [workspaceId],
  );

  const onChangeGpuInputValue = ({ idx, value, initialValue = [] }) => {
    const newState = {};

    const instanceValue = [];

    if (gpuInputValues.length === 0) {
      instanceValue.push(...initialValue);
    } else {
      instanceValue.push(...gpuInputValues);
    }

    checkboxHandler({ idx, flag: !!value });

    const newGpuInputValue = instanceValue.map((v, index) => {
      return index === idx ? value : '';
    });

    setGpuInputValues(newGpuInputValue);
  };

  const modelValidate = useCallback(() => {
    let validation = 0;
    let footerMessage = '';

    const hasTrueWithInput = gpuSelectedOptions.some((item, index) => {
      const isTrue = Object.values(item).includes(true); // data에서 true 확인
      const inputValue = parseFloat(gpuInputValues[index]); // gpuInputValues의 숫자 값

      return isTrue && inputValue >= 1; // true일 때 gpuInputValues 값이 1 이상인지 확인
    });

    if (!hasTrueWithInput) {
      validation++;
      footerMessage = 'trainingInstance.error.message';
    } else if (gpuAllocate === '') {
      validation++;
      footerMessage = 'gpu를 할당해 주세요.';
    }

    setFooterMessage(footerMessage);
    setValidate(validation === 0);
  }, [gpuAllocate, gpuInputValues, gpuSelectedOptions]);

  const isMaxValue = getGpuCalculationResult(
    datasetList,
    gpuSelectedOptions,
    gpuInputValues,
  );

  useEffect(() => {
    modelValidate();
  }, [modelData, modelValidate]);

  useEffect(() => {
    getDataset();
  }, [getDataset]);

  return (
    <NewStyleModalFrame
      title={t('fineTuningResourceSetting.label')}
      type={type}
      submit={{
        text: t('select.label'),
        func: () => {
          postDatasetFiles();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={validate}
      isResize={true}
      isLoading={isLoading}
      isMinimize={true}
      footerMessage={t(footerMessage)}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('instanceAllocation.label')}
          labelSize='large'
        >
          <ResourceSetting
            isInstance
            models={datasetList}
            checkboxHandler={checkboxHandler}
            gpuSelectedOptions={gpuSelectedOptions}
            onChangeGpuInputValue={onChangeGpuInputValue}
            inputValue={gpuInputValues}
            edit={type === 'EDIT_TRAININGS'}
            colList={colList}
            type={'gpu'}
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={`${t('gpuAllocation.label')}`}
          labelSize='large'
          // labelDescText={gpuModelName}
          labelDescStyle={{
            fontSize: '12px',
            color: '#747474',
            marginLeft: '8px',
            transform: 'translateY(-2px)',
          }}
        >
          <InputNumber
            name='gpuInput'
            placeholder={`${t('currentAvailableCount')}`}
            // placeholder={`${t('currentAvailableCount')} : ${gpuMaxTotal}`}
            min={0}
            max={isMaxValue}
            value={gpuAllocate}
            onChange={(e) => {
              let inputValue = e.value;
              setGpuAllocate(inputValue);
            }}
          />
          <div className={cx('warning')}>{t('gpuFineTuning.warning')}</div>
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default FineTuningSettingModal;
