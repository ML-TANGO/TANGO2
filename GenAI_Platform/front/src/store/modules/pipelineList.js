import { createAction, handleActions } from 'redux-actions';

const SET_PIPELINE_STATE = 'pipeline/set';
const GET_PIPELINE_STATE = 'pipeline/get';
const RESET_PIPELINE_STATE = 'playground/reset';

export const handleSetPipelineState = createAction(SET_PIPELINE_STATE);
export const handleGetPipelineState = createAction(GET_PIPELINE_STATE);
export const handleReset = createAction(RESET_PIPELINE_STATE);

// ** llm Playground 값 조절 **
export const pipelineState = {
  preprocessing_task: [],
  deployment_task: [],
  project_task: [],
  isStopBtn: false,
};

export default handleActions(
  {
    [handleSetPipelineState]: (state, action) => {
      const { type, data } = action.payload;
      const { preprocessing_task, deployment_task, project_task, isStopBtn } =
        data;

      if (type === 'pre') return { ...state, preprocessing_task };
      if (type === 'train') return { ...state, project_task };
      if (type === 'development') return { ...state, deployment_task };
      if (type === 'isStopBtn') return { ...state, isStopBtn };
      if (type === 'all') return { ...state, ...data };
      return state;
    },

    [handleReset]: () => {
      return pipelineState;
    },
  },
  pipelineState,
);
