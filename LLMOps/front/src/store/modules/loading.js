import { handleActions, createAction } from 'redux-actions';

const OPEN_LOADING = 'loading/OPEN_LOADING';
const CLOSE_LOADING = 'loading/CLOSE_LOADING';
const OPEN_MULTI_LOADING = 'loading/OPEN_MULTI_LOADING';
const CLOSE_MULTI_LOADING = 'loading/CLOSE_MULTI_LOADING';
const CLEAR_MULTI_LOADING = 'loading/CLEAR_MULTI_LOADING';

export const openLoading = createAction(OPEN_LOADING);
export const closeLoading = createAction(CLOSE_LOADING);
export const openMultiLoading = createAction(OPEN_MULTI_LOADING);
export const closeMultiLoading = createAction(CLOSE_MULTI_LOADING);
export const clearMultiLoading = createAction(CLEAR_MULTI_LOADING);

const INIT_STATE = {
  bgLoading: { loading: false, text: '' },
  contentsLoading: { loading: false, text: '' },
  multiLoading: {},
};

export default handleActions(
  {
    [OPEN_LOADING]: (state, { payload: { text, target } }) => ({
      ...state,
      [target]: { loading: true, text },
    }),
    [CLOSE_LOADING]: (state, { payload: { target } }) => ({
      ...state,
      [target]: { loading: false, text: '' },
    }),
    [OPEN_MULTI_LOADING]: (state, { payload }) => {
      let newLoadingState = {};
      if (Array.isArray(payload)) {
        payload.forEach((target) => {
          newLoadingState = {
            ...newLoadingState,
            [target]: true,
          };
        });
      } else if (typeof payload === 'string' || typeof payload === 'number') {
        newLoadingState = {
          [payload]: true,
        };
      } else if (typeof payload === 'object') {
        newLoadingState = payload;
      }
      return {
        ...state,
        multiLoading: {
          ...state.multiLoading,
          ...newLoadingState,
        },
      };
    },
    [CLOSE_MULTI_LOADING]: (state, { payload }) => {
      let newLoadingState = {};
      if (Array.isArray(payload)) {
        payload.forEach((target) => {
          newLoadingState = {
            ...newLoadingState,
            [target]: false,
          };
        });
      } else if (typeof payload === 'string' || typeof payload === 'number') {
        newLoadingState = {
          [payload]: false,
        };
      } else if (typeof payload === 'object') {
        newLoadingState = payload;
      }
      return {
        ...state,
        multiLoading: {
          ...state.multiLoading,
          ...newLoadingState,
        },
      };
    },
    [CLEAR_MULTI_LOADING]: (state) => ({
      ...state,
      multiLoading: {},
    }),
  },
  INIT_STATE,
);
