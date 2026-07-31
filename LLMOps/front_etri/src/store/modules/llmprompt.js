import { createAction, handleActions } from 'redux-actions';

const SET_PROMPT_STATE = 'llmprompt/set';
const RESET_PROMPT_STATE = 'llmprompt/reset';

export const handleSetPromptState = createAction(SET_PROMPT_STATE);
export const handlePromptReset = createAction(RESET_PROMPT_STATE);

// ** llm Playground 값 조절 **
export const initialPromptState = {
  info: {
    name: '-',
    description: '-',
    create_datetime: '0000-00-00 00:00:00',
    update_datetime: '0000-00-00 00:00:00',
    owner: '-',
    system_message: '',
    user_message: '',
  },
  originInfo: {
    name: '-',
    commit: {
      message: '',
      id: null,
    },
    description: '-',
    create_datetime: '0000-00-00 00:00:00',
    update_datetime: '0000-00-00 00:00:00',
    owner: '-',
    system_message: '',
    user_message: '',
  },
};

export default handleActions(
  {
    [handleSetPromptState]: (state, action) => {
      const { info, originInfo, type } = action.payload;

      if (type === 'info') return { ...state, info };
      if (type === 'originInfo') return { ...state, originInfo };

      return { ...state, info, originInfo };
    },
    [handlePromptReset]: () => {
      return initialPromptState;
    },
  },
  initialPromptState,
);
