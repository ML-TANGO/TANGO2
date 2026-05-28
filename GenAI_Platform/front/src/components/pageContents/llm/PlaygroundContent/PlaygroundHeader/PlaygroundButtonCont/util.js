import _ from 'lodash';

import {
  getDetailPlayground,
  getPlaygroundCheckAccel,
} from '@src/apis/llm/playground';
import {
  handleSetPlaygroundState,
  initialLLMPlaygroundState,
} from '@src/store/modules/llmPlayground';
import { handleOriginValue } from '@src/store/modules/llmPlaygroundResetValue';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

// ** [계산] 배포가 실행되고 있는지 체크하는 반환 함수 **
export const calIsCompleteRunning = (status) => {
  const { status: playgroundStatus, init_deployment } = status;
  if (playgroundStatus === 'running' && init_deployment) return true;
  return false;
};

// ** [계산] 정지 버튼 유효 **
export const calIsStopBtn = (statusType) => {
  if (statusType === 'stop') return false;
  return true;
};

// ** [계산] 저장 버튼 유효성 검사 **
export const calIsSaveBtn = (
  model,
  rag,
  prompt,
  isEqual,
  statusType,
  isFetchingStatus,
) => {
  const { model_type } = model;
  const { is_rag, rag_id } = rag;
  const { is_prompt, prompt_id, prompt_system_message } = prompt;

  if (isFetchingStatus) return false;

  if (statusType === 'running') {
    if (!isEqual) return false;
  }

  if (!isEqual) return false;
  if (!model_type) return false;
  if (is_rag && !rag_id) return false;
  if (is_prompt) {
    if (!prompt_id && !prompt_system_message && !prompt_system_message) {
      return false;
    }
  }
  return true;
};

// ** [계산] 동등한지 비교하는 계산 함수 **
export const calEqualValue = (info, model, rag, prompt, originValue) => {
  const {
    info: originInfo,
    model: originModel,
    rag: originRag,
    prompt: originPrompt,
  } = originValue;

  if (
    _.isEqual(info, originInfo) &&
    _.isEqual(model, originModel) &&
    _.isEqual(rag, originRag) &&
    _.isEqual(prompt, originPrompt)
  ) {
    return false;
  }
  return true;
};

// ** [GET] 플레이그라운드 데이터 **
export const getDetailPlaygroundInfo = async (dispatch, playgroundId) => {
  const { result, message, status, error } = await getDetailPlayground(
    playgroundId,
  );
  const { data } = await getPlaygroundCheckAccel();

  if (status === STATUS_SUCCESS) {
    const payload = {
      type: 'all',
      info: result.info
        ? {
            id: result.info.id,
            create_datetime: result.info.create_datetime,
            description: result.info.description,
            name: result.info.name,
            owner: result.info.owner,
            update_datetime: result.info.update_datetime,
            access: result.info.access,
            users: result.info.users,
          }
        : initialLLMPlaygroundState.info,
      accellator: data.result === 'running' ? true : false,
      isAccellator: data.result !== 'error' ? true : false,
      info_instance: {
        model: result.info_instance?.model
          ? result.info_instance.model
          : initialLLMPlaygroundState.info_instance.model,
        embedding: result.info_instance?.embedding
          ? result.info_instance?.embedding
          : initialLLMPlaygroundState.info_instance.embedding,
        reranker: result.info_instance?.reranker
          ? result.info_instance.reranker
          : initialLLMPlaygroundState.info_instance.reranker,
        immediately_status: result.info_instance?.immediately_status
          ? result.info_instance.immediately_status
          : initialLLMPlaygroundState.info.immediately_status,
      },
      info_request: result.info_request.method
        ? result.info_request
        : initialLLMPlaygroundState.info_request,
      model: result.model
        ? {
            model_type: result.model.model_type,
            model_huggingface_id: result.model.model_hf_id,
            model_allm_id: result.model.model_allm_id,
            model_allm_name: result.model.model_allm_name,
            model_allm_commit_id: result.model.model_allm_commit_id,
            model_allm_commit_name: result.model.model_allm_commit_name,
            model_temperature: result.model_parameter.temperature,
            model_top_p: result.model_parameter.top_p,
            model_top_k: result.model_parameter.top_k,
            model_repetition_penalty: result.model_parameter.repetition_penalty,
            model_max_new_tokens: result.model_parameter.max_new_tokens,
            description: result.model.description ?? '-',
            commit: result.model.commit ?? '-',
            access: result.model.access ?? '-',
            create_datetime:
              result.model.create_datetime ?? '0000-00-00 00:00:00',
            update_datetime: result.model.update_datetime,
          }
        : initialLLMPlaygroundState.model,
      rag: result.rag
        ? {
            is_rag: !!result.rag.id,
            rag_id: result.rag.id,
            rag_name: result.rag.name ?? '',
            chunk_len: result.rag.chunk_len,
            chunk_max: result.rag.chunk_max,
            docs_total_count: result.rag.docs_total_count,
            docs_total_size: result.rag.docs_total_size,
            rag_doc_list: result.rag.rag_doc_list,
            embedding_huggingface_model_id:
              result.rag.embedding_huggingface_model_id,
            reranker_huggingface_model_id:
              result.rag.reranker_huggingface_model_id,
          }
        : initialLLMPlaygroundState.rag,
      prompt: result.prompt
        ? {
            is_prompt: !!result.prompt.name,
            prompt_id: result.prompt.id,
            prompt_name: result.prompt.name,
            prompt_commit_name: result.prompt.commit_name,
            prompt_system_message: result.prompt.system_message,
            prompt_user_message: result.prompt.user_message,
          }
        : initialLLMPlaygroundState.prompt,
    };

    dispatch(handleSetPlaygroundState(payload));
    dispatch(handleOriginValue(payload));
  } else {
    errorToastMessage(error, message);
  }
};

// ** [계산] 배포 버튼 유효성 검사 **
export const calIsDeployBtn = (model, rag, prompt, isEqual, statusType) => {
  const { model_type } = model;
  const { is_rag, rag_id } = rag;
  const { is_prompt, prompt_id } = prompt;

  if (statusType === 'running') {
    if (!isEqual) return false;
  }

  if (!model_type) return false;
  if (is_rag && !rag_id) return false;
  if (is_prompt && !prompt_id) return false;

  return !isEqual;
};
