import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector, shallowEqual } from 'react-redux';
import { toast } from 'react-toastify';

import {
  getPlaygroundDeploymentList,
  postDualStart,
  postPlaygroundDeployStart,
  putDualOptions,
} from '@src/apis/llm/playground';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';
import DualModelInstance from './DualModelInstance';
import ModelInstance from './ModelInstance';
import RagModelInstance from './RagInbedingModelInstance';
import RagrerankerModelInstance from './RagrerankerModelInstance/RagrerankerModelInstance';

import { errorToastMessage } from '@src/utils';
import {
  calFindValueReturn,
  calGpuAllocateValue,
  calSelectedValue,
} from './util';

import classNames from 'classnames/bind';
import style from './LLMPlaygroundDeployModal.module.scss';

const cx = classNames.bind(style);

// ** 초기 인스턴스 리스트 **
const initial = {
  modelInstance: [],
  inbedingInstance: [],
  rerankerInstance: [],
};

// ** [계산] 체크 된 리스트 **
const calSelectCheckbox = (list, isCheck, idx) => {
  const changeList = list.map((el, index) => {
    return {
      ...el,
      front: {
        ...el.front,
        isCheck: index === idx ? isCheck : false,
        value: 0,
        gpuValue: 0,
      },
    };
  });
  return changeList;
};

// ** [계산] 인스턴스 할당 리스트 **
const calInstanceValue = (changeModelList, value, idx) => {
  const changeList = changeModelList.map((el, index) => {
    return {
      ...el,
      front: {
        isCheck: index === idx ? true : false,
        value: index === idx ? value : 0,
        gpuValue: 0,
      },
    };
  });
  return changeList;
};

// ** [계산] GPU 할당 리스트 **
const calGpuValue = (changeModelList, value, instance_id) => {
  const changeList = changeModelList.map((el) => {
    return {
      ...el,
      front: {
        ...el.front,
        gpuValue: el.instance_id === instance_id ? value : el.front.gpuValue,
      },
    };
  });
  return changeList;
};

const calTooltipGpuAllocate = (list) => {
  const shallowList = list.slice();
  const addTooltipGpuAllocate = shallowList.map((info) => ({
    ...info,
    gpu_allocate: info.gpu_allocate,
    tooltipGpuAllocate: info.gpu_allocate,
  }));
  return addTooltipGpuAllocate;
};

// !! [복잡한 계산] 총량, 할당량 변경될 때 마다 리스트 변경하여 반환
const calTotalGpuAllocateMinus = (list, info1, info2) => {
  if (!list || list.length === 0) return [];
  const { instance_id: id1, front: front1 } = info1;
  const { instance_id: id2, front: front2 } = info2;

  const copyList = list.slice();
  const findIndex1 = copyList.findIndex(
    ({ instance_id }) => instance_id === id1,
  );
  const findIndex2 = copyList.findIndex(
    ({ instance_id }) => instance_id === id2,
  );
  const findValue1 = calFindValueReturn(copyList, findIndex1);
  const findValue2 = calFindValueReturn(copyList, findIndex2);

  if (findIndex1 !== -1 && findIndex1 === findIndex2) {
    copyList[findIndex1] = {
      ...findValue1,
      instance_allocate:
        findValue1.instance_allocate - front1.value - front2.value,
      gpu_allocate: findValue1.gpu_allocate - front1.gpuValue - front2.gpuValue,
    };
    return copyList;
  }

  if (findIndex1 !== -1) {
    copyList[findIndex1] = {
      ...findValue1,
      instance_allocate: findValue1.instance_allocate - front1.value,
      gpu_allocate: findValue1.gpu_allocate - front1.gpuValue,
    };
  }
  if (findIndex2 !== -1) {
    copyList[findIndex2] = {
      ...findValue2,
      instance_allocate: findValue2.instance_allocate - front2.value,
      gpu_allocate: findValue2.gpu_allocate - front2.gpuValue,
    };
  }
  return copyList;
};

// ** footermessage 반환 **
const calFooterMessage = (
  embedding_huggingface_model_id,
  reranker_huggingface_model_id,
  selectedModelValue,
  selectedinbedingModelValue,
  selectedrerankerModelValue,
  t,
) => {
  if (!selectedModelValue.instance_id)
    return t('playground.deploy.model.select.instance');

  if (selectedModelValue.front.gpuValue === '')
    return t('playground.deploy.model.select.gpu');

  if (embedding_huggingface_model_id) {
    if (!selectedinbedingModelValue.instance_id)
      return t('playground.deploy.model.select.raginbeddingmodelinstance');
    if (!selectedinbedingModelValue.front.gpuValue === '')
      return t('playground.deploy.model.select.raginbeddingmodelgpu');
  }

  if (reranker_huggingface_model_id) {
    if (!selectedrerankerModelValue.instance_id)
      return t('playground.deploy.model.select.ragrerankerinstance');
    if (!selectedrerankerModelValue.gpuValue === '')
      return t('playground.deploy.model.select.ragrerankergpu');
  }
  return '';
};

// ** 초기 API GET **
const getPlaygroundInstanceList = async (
  playgroundId,
  isFetching,
  setInstanceList,
) => {
  const { result, message, status, error } = await getPlaygroundDeploymentList(
    +playgroundId,
  );
  if (status === STATUS_SUCCESS) {
    const instanceList = result.map((el) => ({
      ...el,
      front: {
        isCheck: false,
        value: 0,
        gpuValue: 0,
      },
    }));

    setInstanceList({
      modelInstance: instanceList,
      inbedingInstance: instanceList,
      rerankerInstance: instanceList,
    });
  } else {
    errorToastMessage(error, message);
  }
  isFetching.current = false;
};

function DualPlaygroundDeployModal({ type, data }) {
  const dispatch = useDispatch();
  const {
    playgroundId,
    canEdit,
    options = {},
    resources = {},
    onSuccess,
  } = data;
  const [instanceList, setInstanceList] = useState([]);
  const [isFetching, setIsFetching] = useState(true);
  const [selectedInstanceId, setSelectedInstanceId] = useState(
    resources.instanceId ?? null,
  );
  const [promptGpuCount, setPromptGpuCount] = useState(
    resources.promptGpuCount ?? 1,
  );
  const [inferenceGpuCount, setInferenceGpuCount] = useState(
    resources.inferenceGpuCount ?? 1,
  );

  useEffect(() => {
    let cancelled = false;
    setIsFetching(true);
    getPlaygroundDeploymentList(+playgroundId).then(
      ({ result, message, status, error }) => {
        if (cancelled) return;
        if (status === STATUS_SUCCESS) {
          setInstanceList(Array.isArray(result) ? result : []);
        } else {
          errorToastMessage(error, message);
        }
        setIsFetching(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [playgroundId]);

  const selectedInstance = instanceList.find(
    (instance) =>
      String(instance.instance_id) === String(selectedInstanceId),
  );
  // 단일 모달과 같은 /playgrounds/instance 계약의 총량으로 두 역할의 합계를 검증한다.
  const gpuCapacity =
    (selectedInstance?.instance_allocate ?? 0) *
    (selectedInstance?.gpu_allocate ?? 0);
  const requestedGpu =
    Number(promptGpuCount || 0) + Number(inferenceGpuCount || 0);
  const footerMessage = !canEdit
    ? '중지 상태에서만 배포 구성을 변경할 수 있습니다.'
    : !selectedInstance
      ? '배포할 인스턴스를 선택해주세요.'
      : requestedGpu > gpuCapacity
        ? `LLM1과 LLM2의 GPU 합계가 인스턴스 용량을 초과합니다. (${requestedGpu}/${gpuCapacity})`
        : '';
  const validate = !isFetching && footerMessage === '';

  const submit = {
    text: '배포',
    func: async () => {
      if (!validate) return false;
      try {
        const { isInferenceExternal, ...savedOptions } = options;
        const optionsResponse = await putDualOptions({
          ...savedOptions,
          playground_id: +playgroundId,
          model_instance_id: +selectedInstanceId,
          prompt_gen_gpu_count: Number(promptGpuCount || 0),
          inference_gpu_count: Number(inferenceGpuCount || 0),
          // 외부 SDS는 생성 파라미터를 읽지 않으므로 기존 규칙대로 null을 보낸다.
          inference_params: isInferenceExternal
            ? null
            : savedOptions.inference_params,
        });
        if (optionsResponse.status !== STATUS_SUCCESS) {
          errorToastMessage(optionsResponse.error, optionsResponse.message);
          return false;
        }

        const startResponse = await postDualStart(+playgroundId);
        if (startResponse.status !== STATUS_SUCCESS) {
          errorToastMessage(startResponse.error, startResponse.message);
          return false;
        }

        await onSuccess?.({
          instanceId: selectedInstanceId,
          promptGpuCount: Number(promptGpuCount || 0),
          inferenceGpuCount: Number(inferenceGpuCount || 0),
        });
        dispatch(closeModal(type));
      } catch (error) {
        errorToastMessage(null, '이중모델 배포 중 오류가 발생했습니다.');
        return false;
      }
      return undefined;
    },
  };

  return (
    <NewStyleModalFrame
      type={type}
      title='배포 자원 설정'
      validate={validate}
      isResize={true}
      isMinimize={true}
      cancel={{ text: '취소' }}
      submit={submit}
      footerMessage={footerMessage}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('flex-32')}>
        <DualModelInstance
          isFetching={isFetching}
          instanceList={instanceList}
          selectedInstanceId={selectedInstanceId}
          promptGpuCount={promptGpuCount}
          inferenceGpuCount={inferenceGpuCount}
          onSelectInstance={setSelectedInstanceId}
          onPromptGpuChange={setPromptGpuCount}
          onInferenceGpuChange={setInferenceGpuCount}
        />
      </div>
    </NewStyleModalFrame>
  );
}

function SinglePlaygroundDeployModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { playgroundId, isDeployState, getDetailPlaygroundInfo } = data;
  const {
    embedding_huggingface_model_id: raw_embedding,
    reranker_huggingface_model_id: raw_reranker,
    init_deployment,
  } = isDeployState;

  // external partner container 모델은 embedding/reranker 없이 단일 GPU 추론.
  const trainingType = useSelector(
    (state) => state.llmPlayground?.model?.training_type,
    shallowEqual,
  );
  const isExternal = trainingType === 'external';
  // external 일 때 embedding/reranker 섹션 강제 숨김
  const embedding_huggingface_model_id = isExternal ? null : raw_embedding;
  const reranker_huggingface_model_id = isExternal ? null : raw_reranker;

  // ** INSTANCE LIST **
  const [instanceList, setInstanceList] = useState(initial);
  const { modelInstance, inbedingInstance, rerankerInstance } = instanceList;

  const modelInstnace2 = calTooltipGpuAllocate(modelInstance);
  const inbedingInstance2 = calTooltipGpuAllocate(inbedingInstance);
  const rerankerInstance2 = calTooltipGpuAllocate(rerankerInstance);

  // ** 선택된 값들 **
  const selectedModelValue = calSelectedValue(modelInstnace2);
  const selectedinbedingModelValue = calSelectedValue(inbedingInstance2);
  const selectedrerankerModelValue = calSelectedValue(rerankerInstance2);

  // ** GPU 할당량 **
  const modelGpuValue = calGpuAllocateValue(selectedModelValue);
  const inbedingGpuValue = calGpuAllocateValue(selectedinbedingModelValue);
  const rerankerGpuValue = calGpuAllocateValue(selectedrerankerModelValue);

  // ** [제목, 경고 메세지, 설정 유효성 검사] **
  const title = t('deploymentsOption.label');
  const footerMessage = calFooterMessage(
    embedding_huggingface_model_id,
    reranker_huggingface_model_id,
    selectedModelValue,
    selectedinbedingModelValue,
    selectedrerankerModelValue,
    t,
  );
  const validate = !footerMessage;
  const cancel = useMemo(() => {
    return {
      text: t('cancel.label'),
    };
  }, [t]);
  const submit = {
    text: t('set.label'),
    func: async () => {
      const payload = {
        playground_id: +playgroundId,
        model_instance_id: +selectedModelValue.instance_id,
        model_instance_count: selectedModelValue.front.value,
        model_gpu_count: selectedModelValue.front.gpuValue,
      };

      if (embedding_huggingface_model_id) {
        payload.embedding_instance_id = selectedinbedingModelValue.instance_id;
        payload.embedding_instance_count =
          selectedinbedingModelValue.front.value;
        payload.embedding_gpu_count = selectedinbedingModelValue.front.gpuValue;
      }

      if (reranker_huggingface_model_id) {
        payload.reranker_instance_id = selectedrerankerModelValue.instance_id;
        payload.reranker_instance_count =
          selectedrerankerModelValue.front.value;
        payload.reranker_gpu_count = selectedrerankerModelValue.front.gpuValue;
      }

      if (init_deployment) {
        payload.restart = true;
      }

      const { status, message } = await postPlaygroundDeployStart(payload);
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      } else {
        await getDetailPlaygroundInfo(dispatch, +playgroundId);
        dispatch(closeModal(type));
      }
    },
  };

  // ** [Props로 내려가는 인스턴스 리스트들 (존재 이유 총량, 할당량 할당 값에 따라 변경 됨)]**
  const propsModelList = calTotalGpuAllocateMinus(
    modelInstnace2,
    selectedinbedingModelValue,
    selectedrerankerModelValue,
  );
  const propsInbedingList = calTotalGpuAllocateMinus(
    inbedingInstance2,
    selectedModelValue,
    selectedrerankerModelValue,
  );
  const propsRerankList = calTotalGpuAllocateMinus(
    rerankerInstance2,
    selectedModelValue,
    selectedinbedingModelValue,
  );

  // ** [인스턴스 체크박스 핸들러] **
  const handleCheckbox = useCallback((modelType, isCheck, idx) => {
    setInstanceList((prev) => {
      const changeModelList = prev[modelType];
      const checkedList = calSelectCheckbox(changeModelList, isCheck, idx);
      return {
        ...prev,
        [modelType]: checkedList,
      };
    });
  }, []);

  // ** [선택된 인스턴스의 할당량 핸들러] **
  const handleInstanceValue = (modelType, value, idx) => {
    setInstanceList((prev) => {
      const changeModelList = prev[modelType];
      const returnList = calInstanceValue(changeModelList, value, idx);
      return {
        ...prev,
        [modelType]: returnList,
      };
    });
  };

  // ** [선택된 GPU 할당량 핸들러] **
  const handleModelValue = useCallback((value, modelType, instance_id) => {
    setInstanceList((prev) => {
      const changeModelList = prev[modelType];
      const returnList = calGpuValue(changeModelList, value, instance_id);
      return {
        ...prev,
        [modelType]: returnList,
      };
    });
  }, []);

  // !! [초기 사이드 이펙트] **
  const isFetching = useRef(true);
  useEffect(() => {
    getPlaygroundInstanceList(+playgroundId, isFetching, setInstanceList);
  }, [playgroundId]);

  return (
    <NewStyleModalFrame
      type={type}
      title={title}
      validate={validate}
      isResize={true}
      isMinimize={true}
      cancel={cancel}
      submit={submit}
      footerMessage={footerMessage}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('flex-32')}>
        <ModelInstance
          isFetching={isFetching.current}
          instanceType={'modelInstance'}
          instanceList={propsModelList}
          selectedModelValue={selectedModelValue}
          gpuValue={modelGpuValue}
          handleCheckbox={handleCheckbox}
          handleInstanceValue={handleInstanceValue}
          handleModelValue={handleModelValue}
        />
        {embedding_huggingface_model_id && (
          <RagModelInstance
            isFetching={isFetching.current}
            instanceType={'inbedingInstance'}
            instanceList={propsInbedingList}
            selectedModelValue={selectedinbedingModelValue}
            gpuValue={inbedingGpuValue}
            handleCheckbox={handleCheckbox}
            handleInstanceValue={handleInstanceValue}
            handleModelValue={handleModelValue}
          />
        )}
        {reranker_huggingface_model_id && (
          <RagrerankerModelInstance
            isFetching={isFetching.current}
            instanceType={'rerankerInstance'}
            instanceList={propsRerankList}
            selectedModelValue={selectedrerankerModelValue}
            gpuValue={rerankerGpuValue}
            handleCheckbox={handleCheckbox}
            handleInstanceValue={handleInstanceValue}
            handleModelValue={handleModelValue}
          />
        )}
      </div>
    </NewStyleModalFrame>
  );
}

export default function LLMPlaygroundDeployModal(props) {
  // 기존 PLAYGROUND_DEPLOY 라우팅은 유지하고 data.mode만으로 안전하게 본문을 분기한다.
  if (props.data?.mode === 'dual') {
    return <DualPlaygroundDeployModal {...props} />;
  }
  return <SinglePlaygroundDeployModal {...props} />;
}
