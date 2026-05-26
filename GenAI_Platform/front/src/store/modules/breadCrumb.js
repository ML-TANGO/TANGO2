import { handleActions, createAction } from 'redux-actions';

const START_PATH = 'START_PATH';
const RESET_PATH = 'RESET_PATH';

export const startPath = createAction(START_PATH);
export const resetPath = createAction(RESET_PATH);

export default handleActions(
  {
    [START_PATH]: (state, action) => {
      return action.payload;
    },
  },
  {
    [RESET_PATH]: (state, action) => {
      return action.payload;
    },
  },
);
