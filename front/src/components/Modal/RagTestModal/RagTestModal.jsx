import {
  getPlaygroundDeploymentList,
  postPlaygroundDeployStart,
} from '@src/apis/llm/playground';
import {
  getRagOptionInstance,
  getRagSetting,
  postRagDeployment,
} from '@src/apis/llm/rag';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { onClickSave } from '@src/components/pageContents/llm/RagContent/RagHeader/RagHeader';

import { closeModal } from '@src/store/modules/modal';

import { STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';
import {
  calFindValueReturn,
  calGpuAllocateValue,
  calSelectedValue,
} from './util';

import NewStyleModalFrame from '../NewStyleModalFrame';
import RagModelInstance from './RagInbedingModelInstance';
import RagrerankerModelInstance from './RagrerankerModelInstance/RagrerankerModelInstance';

import classNames from 'classnames/bind';
import style from './RagTestModal.module.scss';

const cx = classNames.bind(style);

// ** 초기 인스턴스 리스트 **
const initial = {
  inbedingInstance: [],
  rerankerInstance: [],
};

// ** post setting

// POST Submit Model
const postSetting = async (payload, dispatch) => {
  const res = await postRagDeployment(payload);
  const { result, error, message, status } = res;
  if (status === STATUS_SUCCESS) {
    dispatch(closeModal('RAG_TEST_MODAL'));
  } else {
    errorToastMessage(error, message);
  }
};

// ** 새롭게 get 해서 embedding model 체크 **
const onCheckSave = async (ragId) => {
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
  rerankerModel,
  selectedinbedingModelValue,
  selectedrerankerModelValue,
) => {
  if (!selectedinbedingModelValue.instance_id)
    return 'llm.rag.embedding.instance.warn.message';
  if (selectedinbedingModelValue.front.value === 0)
    return 'llm.rag.embedding.instance.value.message';
  // if (!selectedinbedingModelValue.front.gpuValue)
  //   return 'llm.rag.embedding.gpu.warn.message';

  if (rerankerModel) {
    if (!selectedrerankerModelValue.instance_id)
      return 'llm.rag.reranker.instance.warn.message';

    if (selectedrerankerModelValue.front.value === 0)
      return 'llm.rag.reranker.instance.value.message';
    // if (!selectedrerankerModelValue.front.gpuValue)
    //   return 'llm.rag.reranker.gpu.warn.message';
  }
  return '';
};

// ** 초기 API GET **
const getRagInstance = async (ragId, setInstanceList) => {
  const { result, message, status, error } = await getRagOptionInstance(+ragId);
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
      inbedingInstance: instanceList,
      rerankerInstance: instanceList,
    });
  } else {
    errorToastMessage(error, message);
  }
};

export default function RagTestModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { workspaceId, refresh, ragId, git, onSubmit, urlType } = data;

  const { setting, instance, info } = useSelector(
    (state) => state.llmRag,
    shallowEqual,
  );

  const {
    chunk_len: chunkLen,
    doc_list: docList,
    embedding_model: embeddingModel,
    reranker_model: rerankerModel,
    embedding_token: embeddingToken,
    reranker_token: rerankerToken,
  } = setting;

  // ** INSTANCE LIST **
  const [instanceList, setInstanceList] = useState(initial);
  const { modelInstance, inbedingInstance, rerankerInstance } = instanceList;

  const modelInstance2 = calTooltipGpuAllocate([]);
  const inbedingInstance2 = calTooltipGpuAllocate(inbedingInstance);
  const rerankerInstance2 = calTooltipGpuAllocate(rerankerInstance);

  // ** 선택된 값들 **
  const selectedModelValue = calSelectedValue(modelInstance2);
  const selectedinbedingModelValue = calSelectedValue(inbedingInstance2);
  const selectedrerankerModelValue = calSelectedValue(rerankerInstance2);

  // ** GPU 할당량 **

  const inbedingGpuValue = calGpuAllocateValue(selectedinbedingModelValue);
  const rerankerGpuValue = calGpuAllocateValue(selectedrerankerModelValue);

  // ** [제목, 경고 메세지, 설정 유효성 검사] **
  const title = t('llm.rag.resource.setting.label');

  const footerMessage = calFooterMessage(
    rerankerModel,
    selectedinbedingModelValue,
    selectedrerankerModelValue,
  );

  const validate = !footerMessage;

  const cancel = useMemo(() => {
    return {
      text: t('cancel.label'),
    };
  }, [t]);

  const submit = {
    text: t('select.label'),
    func: async () => {
      const checkSave = await onCheckSave(ragId);

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

      const payload = { ragId, type: urlType };

      payload.embeddingId = selectedinbedingModelValue.instance_id;
      payload.embeddingCount = selectedinbedingModelValue.front.value;
      payload.embeddingGpuCount = selectedinbedingModelValue.front.gpuValue;

      if (rerankerModel) {
        payload.rerankerId = selectedrerankerModelValue.instance_id;
        payload.rerankerCount = selectedrerankerModelValue.front.value;
        payload.rerankerGpuCount = selectedrerankerModelValue.front.gpuValue;
      }

      await postSetting(payload, dispatch);
    },
  };

  // ** [Props로 내려가는 인스턴스 리스트들 (존재 이유 총량, 할당량 할당 값에 따라 변경 됨)]**
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
  useEffect(() => {
    getRagInstance(+ragId, setInstanceList);
  }, [ragId]);

  return (
    <NewStyleModalFrame
      type={type}
      title={title}
      validate={validate}
      isResize={true}
      isMinimize={true}
      cancel={cancel}
      submit={submit}
      footerMessage={t(footerMessage)}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('flex-32')}>
        <RagModelInstance
          instanceType={'inbedingInstance'}
          instanceList={propsInbedingList}
          selectedModelValue={selectedinbedingModelValue}
          gpuValue={inbedingGpuValue}
          handleCheckbox={handleCheckbox}
          handleInstanceValue={handleInstanceValue}
          handleModelValue={handleModelValue}
        />

        {rerankerModel && (
          <RagrerankerModelInstance
            instanceType={'rerankerInstance'}
            instanceList={propsRerankList}
            selectedModelValue={selectedrerankerModelValue}
            gpuValue={rerankerGpuValue}
            handleCheckbox={handleCheckbox}
            handleInstanceValue={handleInstanceValue}
            handleModelValue={handleModelValue}
          />
        )}
        <div className={cx('recommend')}>{t('llm.rag.ram.usage.message')}</div>
        <div>
          <div className={cx('warn')}>{t('llm.rag.notice.message')}</div>
          <div className={cx('warn')}>{t('llm.rag.caution.message')}</div>
        </div>
      </div>
    </NewStyleModalFrame>
  );
}
