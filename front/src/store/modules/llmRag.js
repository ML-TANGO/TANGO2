import { createAction, handleActions } from 'redux-actions';

const SET_RAG_STATE = 'llmRag/set';
const GET_RAG_STATE = 'llmRag/get';
const RESET_RAG_STATE = 'llmRag/reset';

export const handleSetRagState = createAction(SET_RAG_STATE);
export const handleGetRagState = createAction(GET_RAG_STATE);
export const handleRagReset = createAction(RESET_RAG_STATE);

// ** llm Rag 값 조절 **
export const initialRagState = {
  setting: {
    chunk_len: 0,
    embedding_model: '-',
    reranker_model: null,
    doc_list: [],
    embedding_token: null,
    reranker_token: null,
  },
  info: {
    name: '-',
    owner: '-',
    update_datetime: '0000-00-00 00:00:00',
    create_datetime: '0000-00-00 00:00:00',
    id: 0,
    description: null,
  },
  instance: {
    embedding: null,
    reranker: null,
  },
  settingStatus: null,
  searchStatus: null,
  rerankerSwitch: false,
  searchOutput: null,
  originSetting: {
    name: '-',
    description: '-',
    create_datetime: '0000-00-00 00:00:00',
    update_datetime: '0000-00-00 00:00:00',
    owner: '-',
    system_message: '',
    user_message: '',
    files: [],
    chunk: 0,
    embedding: [],
    ranker: false,
  },
};

export default handleActions(
  {
    [handleSetRagState]: (state, action) => {
      const {
        setting,
        info,
        instance,
        originSetting,
        type,
        settingStatus,
        searchStatus,
        rerankerSwitch,
        searchOutput,
      } = action.payload;

      if (type === 'setting') return { ...state, setting };
      if (type === 'info') return { ...state, info };
      if (type === 'instance') return { ...state, instance };
      if (type === 'settingStatus') return { ...state, settingStatus };
      if (type === 'searchStatus') return { ...state, searchStatus };
      if (type === 'rerankerSwitch') return { ...state, rerankerSwitch };
      if (type === 'searchOutput') return { ...state, searchOutput };
      if (type === 'originSetting') return { ...state, originSetting };

      return {
        ...state,
        setting,
        info,
        instance,
        originSetting,
        rerankerSwitch,
        settingStatus,
        searchStatus,
        searchOutput,
      };
    },
    [handleGetRagState]: (state, action) => {
      const {
        setting,
        info,
        instance,
        settingStatus,
        searchStatus,
        searchOutput,
      } = state;

      if (action.payload === 'info') return info;
      if (action.payload === 'setting') return setting;
      if (action.payload === 'instance') return instance;
      if (action.payload === 'status') return instance;
      if (action.payload === 'settingStatus') return settingStatus;
      if (action.payload === 'searchStatus') return searchStatus;
      if (action.payload === 'searchOutput') return searchOutput;
      return state;
    },
    [handleRagReset]: () => {
      return initialRagState;
    },
  },
  initialRagState,
);
