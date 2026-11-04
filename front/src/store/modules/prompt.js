import { createAction, handleActions } from 'redux-actions';

const SET_PROMPT = 'prompt/SET_PROMPT';
const CLEAR_PROMPT = 'prompt/CLEAR_PROMPT';

export const setPrompt = createAction(SET_PROMPT);
export const clearPrompt = createAction(CLEAR_PROMPT);

const INIT_STATE = {
  isPrompt: false,
  message: '',
};

export default handleActions(
  {
    [SET_PROMPT]: (_, { payload: message }) => ({
      isPrompt: true,
      message,
    }),
    [CLEAR_PROMPT]: () => ({
      isPrompt: false,
      message: '',
    }),
  },
  INIT_STATE,
);
