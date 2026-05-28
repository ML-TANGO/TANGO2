// import { createAction, handleActions } from 'redux-actions';

// const START_LOADING = 'uploadLoading/START_LOADING';
// const STOP_LOADING = 'uploadLoading/STOP_LOADING';

// export const startDatasetLoading = createAction(START_LOADING);
// export const stopDatasetLoading = createAction(STOP_LOADING);

// const INIT_STATE = false;

// const INIT_STATE2 = {};

// export default handleActions(
//   {
//     [START_LOADING]: (state, action) => true, // 로딩 시작 시 상태를 true로 설정
//     [STOP_LOADING]: (state, action) => false, // 로딩 중지 시 상태를 false로 설정
//   },
//   INIT_STATE,
// );

import { createAction, handleActions } from 'redux-actions';

// Action Types
const START_LOADING = 'uploadLoading/START_LOADING';
const STOP_LOADING = 'uploadLoading/STOP_LOADING';
const START_UPLOADING = 'uploadLoading/START_UPLOADING';
const STOP_UPLOADING = 'uploadLoading/STOP_UPLOADING';
const ADD_WORKER = 'uploadLoading/ADD_WORKER';
const REMOVE_WORKER = 'uploadLoading/REMOVE_WORKER';
const CLEAR_WORKERS = 'uploadLoading/CLEAR_WORKERS';

// Action Creators
export const startDatasetLoading = createAction(START_LOADING);
export const stopDatasetLoading = createAction(STOP_LOADING);
export const startUploading = createAction(START_UPLOADING);
export const stopUploading = createAction(STOP_UPLOADING);
export const addWorker = createAction(
  ADD_WORKER,
  (id, path, fileName, worker) => ({
    key: `${id}:${path}:${fileName}`, // id, path, filename을 결합한 고유 키 - 더 좋고 간단한 방법 있으면 변경
    worker,
  }),
);
export const removeWorker = createAction(
  REMOVE_WORKER,
  (id, path, fileName) => ({
    key: `${id}:${path}:${fileName}`, // id, path, filename을 결합한 고유 키로 워커 찾기
  }),
);
export const clearWorkers = createAction(CLEAR_WORKERS);

// Initial State
const INIT_STATE = {
  isLoading: false,
  isUploading: false,
  activeWorkers: new Map(), // 워커를 관리하는 Map 객체 {File Name : Worker Info}
};

// Reducer
export default handleActions(
  {
    [START_LOADING]: (state) => ({
      ...state,
      isLoading: true,
    }),
    [STOP_LOADING]: (state) => ({
      ...state,
      isLoading: false,
    }),
    [START_UPLOADING]: (state) => ({
      ...state,
      isUploading: true,
    }),
    [STOP_UPLOADING]: (state) => ({
      ...state,
      isUploading: false,
    }),
    [ADD_WORKER]: (state, { payload: { key, worker } }) => {
      const newActiveWorkers = new Map(state.activeWorkers);
      newActiveWorkers.set(key, worker);
      return {
        ...state,
        activeWorkers: newActiveWorkers,
      };
    },
    [REMOVE_WORKER]: (state, { payload: { key } }) => {
      const newActiveWorkers = new Map(state.activeWorkers);
      newActiveWorkers.delete(key);
      return {
        ...state,
        activeWorkers: newActiveWorkers,
      };
    },
    [CLEAR_WORKERS]: (state) => ({
      ...state,
      activeWorkers: new Map(),
    }),
  },
  INIT_STATE,
);
