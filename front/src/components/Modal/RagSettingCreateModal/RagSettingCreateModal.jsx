import { InputNumber, InputText, Radio, Textarea } from '@jonathan/ui-react';

import {
  getRagOptionInstance,
  getRagSetting,
  postRagDeployment,
} from '@src/apis/llm/rag';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ResourceSetting from '@src/components/molecules/ResourceSetting';
import { onClickSave } from '@src/components/pageContents/llm/RagContent/RagHeader/RagHeader';
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { copyToClipboard, errorToastMessage } from '@src/utils';

import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './RagSettingCreateModal.module.scss';

const cx = classNames.bind(style);

const RagSettingCreateModal = ({ data, type }) => {
  const { workspaceId, refresh, ragId, git, onSubmit, urlType } = data;
  const { t } = useTranslation();

  const col1 = t('instanceName.label');

  const col2 = <div>{t('totalAmount.label')}</div>;

  const col3 = <div>{t('allocation.label')}</div>;

  const colList = [col1, col2, col3];
  const dispatch = useDispatch();

  const { setting, instance, info } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );

  const [embeddingList, setEmbeddingList] = useState([]);
  const [originRerankerList, setOriginRerankerList] = useState([]);
  const [rerankerList, setRerankerList] = useState([]);

  //
  const [embeddingSelectedOptions, setEmbeddingSelectedOptions] = useState([]);
  const [rerankerSelectedOptions, setRerankerSelectedOptions] = useState([]);

  //
  const [embeddingInputValues, setEmbeddingInputValues] = useState([]);
  const [rerankerInputValues, setRerankerInputValues] = useState([]);

  const [embeddingGpu, setEmbeddingGpu] = useState('');
  const [rerankerGpu, setRerankerGpu] = useState('');

  const [isLoading, setIsLoading] = useState(false);

  const [validate, setValidate] = useState(false);

  const {
    chunk_len: chunkLen,
    doc_list: docList,
    embedding_model: embeddingModel,
    reranker_model: rerankerModel,
    embedding_token: embeddingToken,
    reranker_token: rerankerToken,
  } = setting;

  const embeddingCheckboxHandler = ({ idx, flag, initialValue = [] }) => {
    let selectedInstance = [];

    if (embeddingSelectedOptions.length === 0) {
      selectedInstance.push(...initialValue);
    } else {
      selectedInstance.push(...embeddingSelectedOptions);
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
      const newGpuInputValues = [...embeddingInputValues];
      newGpuInputValues[idx] = '';

      setEmbeddingInputValues(newGpuInputValues);
    } else {
      const newGpuValues = [...embeddingInputValues].map(
        (inputVal, index) => '',
      );
      newState.gpuInputValues = newGpuValues;
      setEmbeddingInputValues(newGpuValues);
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
    setEmbeddingSelectedOptions(result);
  };

  const rerankerCheckboxHandler = ({ idx, flag, initialValue = [] }) => {
    let selectedInstance = [];

    if (rerankerSelectedOptions.length === 0) {
      selectedInstance.push(...initialValue);
    } else {
      selectedInstance.push(...rerankerSelectedOptions);
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
      const newGpuInputValues = [...embeddingInputValues];
      newGpuInputValues[idx] = '';

      setRerankerInputValues(newGpuInputValues);
    } else {
      const newGpuValues = [...embeddingInputValues].map(
        (inputVal, index) => '',
      );
      newState.gpuInputValues = newGpuValues;
      setRerankerInputValues(newGpuValues);
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
    setRerankerSelectedOptions(result);
  };

  const onCheckSave = async () => {
    const { result, message, status } = await getRagSetting(ragId);

    if (status === STATUS_SUCCESS) {
      const { info, instance, setting } = result;
      if (setting.embedding_model) {
        // embedding model 이 있었는지 체크 한다.
        return true;
      }
    }
    return false;
  };

  // POST Submit Model
  const postSetting = async () => {
    const embeddingSelectedIndex = embeddingSelectedOptions.findIndex(
      (item) => Object.values(item)[0] === true,
    );
    const embeddingSelectedId =
      embeddingSelectedIndex !== -1
        ? embeddingList[embeddingSelectedIndex].id
        : null;
    const embeddingCount = embeddingInputValues[embeddingSelectedIndex];

    const payload = {
      ragId,
      embeddingId: embeddingSelectedId,
      embeddingCount: embeddingCount,
      embeddingGpuCount: embeddingGpu,
      type: urlType,
    };
    if (rerankerModel) {
      const rerankerSelectedIndex = rerankerSelectedOptions.findIndex(
        (item) => Object.values(item)[0] === true,
      );
      const rerankerSelectedId =
        rerankerSelectedIndex !== -1
          ? rerankerList[rerankerSelectedIndex].id
          : null;
      const rerankerCount = rerankerInputValues[rerankerSelectedIndex];
      payload.rerankerId = rerankerSelectedId;
      payload.rerankerCount = rerankerCount;
      payload.rerankerGpuCout = rerankerGpu;
    }

    const res = await postRagDeployment(payload);
    const { result, error, message, status } = res;
    if (status === STATUS_SUCCESS) {
      dispatch(closeModal('RAG_SETTING_CREATE_MODAL'));
    } else {
      errorToastMessage(error, message);
    }
  };

  // GET instance
  const getDataset = useCallback(async () => {
    const response = await getRagOptionInstance(ragId);

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const newData = result.map((item) => ({
        cpu: item.cpu_allocate,
        gpu: item.gpu_allocate,
        total: item.instance_allocate,
        id: item.instance_id,
        gpu_name: item.gpu_allocate !== 0 ? item.instance_name : false,
        ram: item.ram_allocate,
        name: item.gpu_allocate === 0 ? item.instance_name : item.resource_name,
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

        setEmbeddingSelectedOptions(selectedOptions);
        setRerankerSelectedOptions(selectedOptions);
        // setGpuInputValues(initialInputValues);
        setEmbeddingInputValues(initialInputValues);
        setRerankerInputValues(initialInputValues);
      }

      setEmbeddingList(newData);
      setRerankerList(newData);
      setOriginRerankerList(newData);
    } else {
      errorToastMessage(error, message);
    }
  }, [ragId]);

  const onChangeEmbeddingInputValue = ({ idx, value, initialValue = [] }) => {
    const instanceValue = [];

    if (embeddingInputValues.length === 0) {
      instanceValue.push(...initialValue);
    } else {
      instanceValue.push(...embeddingInputValues);
    }

    embeddingCheckboxHandler({ idx, flag: !!value });

    const newGpuInputValue = instanceValue.map((v, index) => {
      return index === idx ? value : '';
    });

    setEmbeddingInputValues(newGpuInputValue);
  };

  const onChangeRerankerInputValue = ({ idx, value, initialValue = [] }) => {
    const instanceValue = [];

    if (rerankerInputValues.length === 0) {
      instanceValue.push(...initialValue);
    } else {
      instanceValue.push(...rerankerInputValues);
    }

    rerankerCheckboxHandler({ idx, flag: !!value });

    const newGpuInputValue = instanceValue.map((v, index) => {
      return index === idx ? value : '';
    });

    setRerankerInputValues(newGpuInputValue);
  };

  //
  const modelValidate = () => {
    const hasTrueWithEmbedding = embeddingSelectedOptions.some(
      (item, index) => {
        const isTrue = Object.values(item).includes(true); // data에서 true 확인
        const inputValue = parseFloat(embeddingInputValues[index]); // gpuInputValues의 숫자 값

        return isTrue && inputValue >= 1; // true일 때 gpuInputValues 값이 1 이상인지 확인
      },
    );

    if (!hasTrueWithEmbedding)
      return t('llm.rag.embedding.instance.warn.message');
    if (embeddingGpu === 0 || embeddingGpu === '')
      return t('llm.rag.embedding.gpu.warn.message');

    if (rerankerModel) {
      const hasTrueWithReranker = rerankerSelectedOptions.some(
        (item, index) => {
          '';
          const isTrue = Object.values(item).includes(true); // data에서 true 확인
          const inputValue = parseFloat(rerankerInputValues[index]); // gpuInputValues의 숫자 값
          return isTrue && inputValue >= 1; // true일 때 gpuInputValues 값이 1 이상인지 확인
        },
      );
      if (!hasTrueWithReranker)
        return t('llm.rag.reranker.instance.warn.message');
      if (rerankerGpu === 0 || rerankerGpu === '')
        return t('llm.rag.reranker.gpu.warn.message');
    }
    return '';
  };

  useEffect(() => {
    getDataset();
  }, [getDataset]);

  const footerMessage = modelValidate();

  return (
    <NewStyleModalFrame
      title={t('llm.rag.resource.setting.label')}
      type={type}
      submit={{
        text: t('select.label'),
        func: async () => {
          const checkSave = await onCheckSave();

          if (!checkSave) {
            await onClickSave({
              docList,
              ragId,
              chunkLen,
              embeddingModel,
              embeddingToken,
              rerankerModel,
              rerankerToken,
            });
          }

          await postSetting();
        },
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={footerMessage === ''}
      isResize={true}
      isLoading={isLoading}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <div className={cx('label')}>{t('ragEmbeddedModel.label')}</div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('instanceAllocation.label')}
          labelSize='large'
        >
          <ResourceSetting
            isInstance
            models={embeddingList}
            checkboxHandler={embeddingCheckboxHandler}
            gpuSelectedOptions={embeddingSelectedOptions}
            onChangeGpuInputValue={onChangeEmbeddingInputValue}
            inputValue={embeddingInputValues}
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
            max={10} // 선택된 거의 gpu_count * inputvalue
            value={embeddingGpu}
            onChange={(e) => {
              let inputValue = e.value;
              setEmbeddingGpu(inputValue);
            }}
          />
          {/* <div className={cx('warning')}>{t('gpuFineTuning.warning')}</div> */}
        </InputBoxWithLabel>
      </div>

      {rerankerModel && (
        <>
          <div className={cx('bar')} />
          <div className={cx('label')}>{t('ragRerankerModel.label')}</div>
          <div className={cx('row')}>
            <InputBoxWithLabel
              labelText={t('instanceAllocation.label')}
              labelSize='large'
            >
              <ResourceSetting
                isInstance
                models={rerankerList} // o
                checkboxHandler={rerankerCheckboxHandler} // o
                gpuSelectedOptions={rerankerSelectedOptions} // o
                onChangeGpuInputValue={onChangeRerankerInputValue}
                inputValue={rerankerInputValues}
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
                max={10}
                value={rerankerGpu}
                onChange={(e) => {
                  let inputValue = e.value;
                  setRerankerGpu(inputValue);
                }}
              />
              {/* <div className={cx('warning')}>{t('gpuFineTuning.warning')}</div> */}
            </InputBoxWithLabel>
          </div>
        </>
      )}

      <div className={cx('recommend')}>{t('llm.rag.ram.usage.message')}</div>
      <div className={cx('warn')}>{t('llm.rag.notice.message')}</div>
      <div className={cx('warn')}>{t('llm.rag.caution.message')}</div>
    </NewStyleModalFrame>
  );
};

export default RagSettingCreateModal;
