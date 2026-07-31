import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import _ from 'lodash';

import { putDescription, putPlaygroundOptions } from '@src/apis/llm/playground';

import { calEqualValue, calIsSaveBtn, getDetailPlaygroundInfo } from '../util';

const useSaveBtn = (isFetchingStatus, playgroundId) => {
  const dispatch = useDispatch();

  const { status } = useSelector((state) => state.llmPlayground, shallowEqual);
  const { status: statusType } = status;

  const originValue = useSelector(
    (state) => state.llmPlaygroundResetValue,
    shallowEqual,
  );

  const { info, model, rag, prompt } = useSelector(
    (state) => state.llmPlayground,
    shallowEqual,
  );

  const isEqual = calEqualValue(info, model, rag, prompt, originValue);
  const isSaveBtn = calIsSaveBtn(
    model,
    rag,
    prompt,
    isEqual,
    statusType,
    isFetchingStatus,
  );

  const handleSave = async () => {
    const {
      model_type,
      model_huggingface_id,
      model_allm_id,
      model_allm_commit_id,
      model_temperature,
      model_top_p,
      model_top_k,
      model_repetition_penalty,
      model_max_new_tokens,
      description,
      commit,
      access,
      create_datetime,
      update_datetime,
    } = model;

    const body = {
      model_type,
      model_huggingface_id,
      model_allm_id: `${model_allm_id}`,
      model_allm_commit_id: `${model_allm_commit_id}`,
      model_temperature,
      model_top_p,
      model_top_k,
      model_repetition_penalty,
      model_max_new_tokens,
      playground_id: +playgroundId,
      is_rag: rag.is_rag,
      rag_id: rag.rag_id,
      rag_chunk_max: +rag.chunk_max,
      accelerator: info.accelerator,
      model_info: {
        description,
        commit,
        access,
        create_datetime,
        update_datetime,
      },
      ...prompt,
    };

    if (!_.isEqual(info, originValue.info))
      await putDescription({ playgroundId, description: info.description });

    await putPlaygroundOptions(body);
    await getDetailPlaygroundInfo(dispatch, +playgroundId);
  };

  return {
    isSaveBtn,
    handleSave,
  };
};

export default useSaveBtn;
