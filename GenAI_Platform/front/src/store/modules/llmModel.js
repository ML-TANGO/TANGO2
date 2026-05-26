import { createAction, handleActions } from 'redux-actions';

const SET_MODEL_STATE = 'llmModel/set';
const SET_MODEL_RANGE_STATE = 'llmModel/set/range';
const GET_MODEL_STATE = 'llmModel/get';
const RESET_MODEL_STATE = 'llmModel/reset';

export const handleSetModelState = createAction(SET_MODEL_STATE);
export const handleSetModelRangeState = createAction(SET_MODEL_RANGE_STATE);
export const handleGetModelState = createAction(GET_MODEL_STATE);
export const handleModelReset = createAction(RESET_MODEL_STATE);

// ** llm Model 값 조절 **
// ** 다른 페이지와 맞춰서 점차 늘려갈 예정 **
export const initialModelState = {
  info: {
    name: null,
    subName: '',
  },
  range: {
    numberOfEpochs: 3,
    gradientAccumulationSteps: 1,
    cutoffLength: 512,
    learningRate: 0.00005,
    warmupSteps: 100,
  },
  originRange: {
    numberOfEpochs: 3,
    gradientAccumulationSteps: 1,
    cutoffLength: 512,
    learningRate: 0.00005,
    warmupSteps: 100,
  },
};

export default handleActions(
  {
    [handleSetModelState]: (state, action) => {
      const { info, type, range, originRange } = action.payload;

      if (type === 'setting') return { ...state, info };
      if (type === 'range') return { ...state, range };
      if (type === 'originRange') return { ...state, originRange };
      return { ...state, info };
    },
    [handleSetModelRangeState]: (state, action) => {
      const { info, type, range, originRange, modelValue } = action.payload;

      return {
        ...state,
        range: {
          ...state.range,
          [type]: modelValue,
        },
      };
    },
    [handleGetModelState]: (state, action) => {
      const { setting, info, instance, range, originRange } = state;

      if (action.payload === 'info') return info;
      if (action.payload === 'range') return range;
      if (action.payload === 'originRange') return originRange;

      return state;
    },
    [handleModelReset]: () => {
      return initialModelState;
    },
  },
  initialModelState,
);
