import { createAction, handleActions } from 'redux-actions';

import {
  callApi,
  STATUS_FAIL,
  STATUS_INTERNAL_SERVER_ERROR,
  STATUS_SUCCESS,
} from '@src/network';

const prefix = 'workspace';

const SET_WORKSPACE = `${prefix}/SET_WORKSPACE`;
const GET_WORKSPACES_REQ = `${prefix}/GET_WORKSPACES_REQ`;
const GET_WORKSPACES_SUCCESS = `${prefix}/GET_WORKSPACES_SUCCESS`;
const GET_WORKSPACES_FAIL = `${prefix}/GET_WORKSPACES_FAIL`;

export const setWorkspace = createAction(SET_WORKSPACE);
const getWorkspacesReq = createAction(GET_WORKSPACES_REQ);
const getWorkspacesSuccess = createAction(GET_WORKSPACES_SUCCESS);
const getWorkspacesFail = createAction(GET_WORKSPACES_FAIL);

export const getWorkspacesAsync = () => async (dispatch) => {
  dispatch(getWorkspacesReq());

  const { result, message, status } = await callApi({
    url: 'workspaces',
    method: 'get',
  });

  if (status === STATUS_SUCCESS) {
    // 성공
    dispatch(getWorkspacesSuccess(result.list));
  } else if (status === STATUS_FAIL) {
    // 실패
    dispatch(getWorkspacesFail(message));
  } else if (status === STATUS_INTERNAL_SERVER_ERROR) {
    // 서버 에러
    dispatch(getWorkspacesFail(message));
  } else {
    dispatch(getWorkspacesFail(message));
  }
};

const INIT_STATE = {
  workspace: null,
  loading: false,
  workspaces: [],
};

export default handleActions(
  {
    [SET_WORKSPACE]: (state, action) => ({
      ...state,
      workspace: action.payload,
    }),
    [GET_WORKSPACES_REQ]: (state) => ({ ...state, loading: true }),
    [GET_WORKSPACES_SUCCESS]: (state, action) => ({
      ...state,
      workspaces: action.payload.sort((prev, cur) => {
        if (
          prev.favorites > cur.favorites &&
          prev.status !== 'expired' &&
          cur.status !== 'expired'
        ) {
          return -1;
        } else {
          return 1;
        }
      }),
      loading: false,
    }),
    [GET_WORKSPACES_FAIL]: (state) => ({ ...state, loading: false }),
  },
  INIT_STATE,
);
