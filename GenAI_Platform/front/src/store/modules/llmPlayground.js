import { createAction, handleActions } from 'redux-actions';

const SET_PLAYGROUND_STATE = 'playground/set';
const SET_PLAYGROUND_MODEL_STATE = 'playground/set/model';
const SET_PLAYGROUND_RAG_STATE = 'playground/set/rag';

const GET_PLAYGROUND_STATE = 'playground/get';
const RESET_PLAYGROUND_STATE = 'playground/reset';

export const handleSetPlaygroundState = createAction(SET_PLAYGROUND_STATE);
export const handleSetModelValue = createAction(SET_PLAYGROUND_MODEL_STATE);
export const handleSetRagValue = createAction(SET_PLAYGROUND_RAG_STATE);

export const handleGetPlaygroundState = createAction(GET_PLAYGROUND_STATE);
export const handleReset = createAction(RESET_PLAYGROUND_STATE);

// ** llm Playground 값 조절 **
export const initialLLMPlaygroundState = {
  info: {
    id: null,
    create_datetime: '0000-00-00 00:00:00',
    description: '-',
    name: '-',
    owner: '-',
    update_datetime: '0000-00-00 00:00:00',
    access: 1,
    users: [],
  },
  accellator: false,
  isAccellator: false,
  info_instance: {
    model: {
      instance_id: 0,
      instance_type: 'GPU',
      instance_name: '-',
      instance_allocate: 0,
      gpu_allocate: 0,
      gpu_available: true,
      cpu_allocate: 0,
      cpu_available: true,
      ram_allocate: 0,
      ram_available: true,
      instance_available: true,
      description: '-',
      commit: '-',
      access: true,
      create_datetime: '0000-00-00 00:00:00',
      update_datetime: '0000-00-00 00:00:00',
    },
    embedding: {
      instance_id: 0,
      instance_type: 'GPU',
      instance_name: '-',
      instance_allocate: 0,
      gpu_allocate: 0,
      gpu_available: true,
      cpu_allocate: 0,
      cpu_available: true,
      ram_allocate: 0,
      ram_available: true,
      instance_available: true,
    },
    reranker: {
      instance_id: 0,
      instance_type: 'GPU',
      instance_name: '-',
      instance_allocate: 0,
      gpu_allocate: 0,
      gpu_available: true,
      cpu_allocate: 0,
      cpu_available: true,
      ram_allocate: 0,
      ram_available: true,
      instance_available: true,
    },
    immediately_status: true,
  },
  model: {
    model_type: '',
    model_huggingface_id: '',
    model_allm_name: '',
    model_allm_id: '',
    model_allm_commit_id: '',
    model_allm_commit_name: '',
    training_type: '',
    model_temperature: 1,
    model_top_p: 0.9,
    model_top_k: 50,
    model_repetition_penalty: 1.2,
    model_max_new_tokens: 512,
  },
  rag: {
    is_rag: false,
    rag_id: null,
    rag_name: '',
    chunk_len: 0,
    chunk_max: 0,
    docs_total_count: 0,
    docs_total_size: 0,
    rag_doc_list: [],
    embedding_huggingface_model_id: '',
    reranker_huggingface_model_id: '',
  },
  prompt: {
    is_prompt: false,
    prompt_id: null,
    prompt_name: '',
    prompt_commit_name: '',
    prompt_system_message: '',
    prompt_user_message: '',
  },
  status: {
    status: '',
    init_deployment: false,
  },
  info_request: {
    format: [],
    method: '',
    url: '-',
  },
};

export default handleActions(
  {
    [handleSetPlaygroundState]: (state, action) => {
      const {
        type,
        info,
        accellator,
        isAccellator,
        info_instance,
        model,
        rag,
        prompt,
        status,
        info_request,
      } = action.payload;
      if (type === 'model') return { ...state, model };
      if (type === 'info') return { ...state, info };
      if (type === 'accellator') return { ...state, accellator };
      if (type === 'rag') return { ...state, rag };
      if (type === 'prompt')
        return {
          ...state,
          prompt: {
            ...state.prompt,
            ...prompt,
          },
        };
      if (type === 'status') return { ...state, status };
      return {
        ...state,
        info_request,
        model,
        info,
        accellator,
        isAccellator,
        info_instance,
        rag,
        prompt,
      };
    },
    [handleSetModelValue]: (state, action) => {
      const { type, modelValue } = action.payload;

      return {
        ...state,
        model: {
          ...state.model,
          [type]: modelValue,
        },
      };
    },
    [handleSetRagValue]: (state, action) => {
      const { type, ragValue } = action.payload;
      return {
        ...state,
        rag: {
          ...state.rag,
          [type]: ragValue,
        },
      };
    },
    [handleGetPlaygroundState]: (state, action) => {
      const { rag, info, model, prompt } = state;

      if (action.payload === 'info') return info;
      if (action.payload === 'model') return model;
      if (action.payload === 'rag') return rag;
      if (action.payload === 'prompt') return prompt;
      return state;
    },
    [handleReset]: () => {
      return initialLLMPlaygroundState;
    },
  },
  initialLLMPlaygroundState,
);
