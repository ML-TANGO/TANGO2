import { combineReducers } from 'redux';

import alarmNotice from './alarmNotice';
import auth from './auth';
import breadCrumb from './breadCrumb';
import confirm from './confirm';
import download from './download';
import headerOptions from './headerOptions';
import llmModel from './llmModel';
import llmPlayground from './llmPlayground';
import llmPlaygroundResetValue from './llmPlaygroundResetValue';
import llmprompt from './llmprompt';
import llmRag from './llmRag';
import loading from './loading';
import modal from './modal';
import nav from './nav';
import pipelineList from './pipelineList';
import popup from './popup';
import popupState from './popupState';
import progressList from './progressList';
import prompt from './prompt';
import tab from './tab';
import upload from './upload';
import uploadLoading from './uploadLoading';
import workspace from './workspace';

const appReducer = combineReducers({
  auth,
  modal,
  confirm,
  nav,
  workspace,
  loading,
  tab,
  upload,
  prompt,
  progressList,
  download,
  breadCrumb,
  headerOptions,
  popup,
  alarmNotice,
  uploadLoading,
  popupState,
  llmPlayground,
  llmPlaygroundResetValue,
  llmprompt,
  llmRag,
  llmModel,
  pipelineList,
});

const rootReducer = (state, action) => {
  if (
    action.type === 'auth/LOGOUT_REQUEST' ||
    action.type === 'auth/RESET_STATE'
  )
    return appReducer(undefined, action);
  return appReducer(state, action);
};

export default rootReducer;
