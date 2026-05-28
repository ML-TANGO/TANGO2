import { handleActions, createAction } from 'redux-actions';

const OPEN_DOWNLOAD_PROGRESS = 'download/OPEN_DOWNLOAD_PROGRESS';
const CLOSE_DOWNLOAD_PROGRESS = 'download/CLOSE_DOWNLOAD_PROGRESS';
const SET_DOWNLOAD_PROGRESS = 'download/SET_DOWNLOAD_PROGRESS';

export const openDownloadProgress = createAction(OPEN_DOWNLOAD_PROGRESS);
export const closeDownloadProgress = createAction(CLOSE_DOWNLOAD_PROGRESS);
export const setDownloadProgress = createAction(SET_DOWNLOAD_PROGRESS);

const INIT_STATE = {
  downloadProgress: 0,
  isOpen: false,
};

export default handleActions(
  {
    [OPEN_DOWNLOAD_PROGRESS]: (state) => ({
      ...state,
      isOpen: true,
    }),
    [SET_DOWNLOAD_PROGRESS]: (state, { payload: downloadProgress }) => ({
      ...state,
      downloadProgress,
    }),
    [CLOSE_DOWNLOAD_PROGRESS]: () => ({
      isOpen: false,
      downloadProgress: 0,
    }),
  },
  INIT_STATE,
);
