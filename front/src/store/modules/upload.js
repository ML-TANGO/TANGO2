import { handleActions, createAction } from 'redux-actions';

const prefix = 'upload/';

const OPEN_UPLOAD_LIST = `${prefix}OPEN_UPLOAD_LIST`;
const CLOSE_UPLOAD_LIST = `${prefix}CLOSE_UPLOAD_LIST`;
const SET_UPLOAD_LIST = `${prefix}SET_UPLOAD_LIST`;
const ADD_UPLOAD_INSTANCE = `${prefix}ADD_UPLOAD_INSTANCE`;
const DELETE_UPLOAD_INSTANCE = `${prefix}DELETE_UPLOAD_INSTANCE`;
const DELETE_UPLOAD_INSTANCE_ALL = `${prefix}DELETE_UPLOAD_INSTANCE_ALL`;
const DELETE_LAST_UPLOAD_INSTANCE = `${prefix}UPLOAD_LIST_LENGTH`;

export const openUploadList = createAction(OPEN_UPLOAD_LIST);
export const closeUploadList = createAction(CLOSE_UPLOAD_LIST);
export const setUploadList = createAction(SET_UPLOAD_LIST);
export const addUploadInstance = createAction(ADD_UPLOAD_INSTANCE);
export const deleteUploadInstance = createAction(DELETE_UPLOAD_INSTANCE);
export const deleteUploadInstanceAll = createAction(DELETE_UPLOAD_INSTANCE_ALL);
export const deleteLastUploadInstance = createAction(
  DELETE_LAST_UPLOAD_INSTANCE,
);

const INIT_STATE = {
  uploadList: [],
  isOpen: false,
};

export default handleActions(
  {
    [OPEN_UPLOAD_LIST]: (state) => ({ ...state, isOpen: true }),
    [CLOSE_UPLOAD_LIST]: (state) => ({
      ...state,
      isOpen: false,
      uploadList: [],
    }),
    [SET_UPLOAD_LIST]: (state, action) => ({
      ...state,
      uploadList: action.payload,
    }),
    [ADD_UPLOAD_INSTANCE]: (state, action) => ({
      ...state,
      uploadList: [...state.uploadList, action.payload],
    }),
    [DELETE_UPLOAD_INSTANCE]: (state, action) => {
      const prevList = state.uploadList;
      const target = action.payload;

      const newList = [
        ...prevList.slice(0, target),
        ...prevList.slice(target + 1, prevList.length),
      ];

      return {
        ...state,
        uploadList: newList,
        isOpen: newList.length !== 0,
      };
    },
    [DELETE_UPLOAD_INSTANCE_ALL]: (state) => ({
      ...state,
      uploadList: [],
    }),
    [DELETE_LAST_UPLOAD_INSTANCE]: (state) => {
      const newList = JSON.parse(JSON.stringify(state.uploadList));
      let isOpen = true;

      if (state.uploadList.length > 0) {
        newList.pop();
      }
      if (newList.length === 0) {
        isOpen = false;
      }
      return {
        ...state,
        isOpen,
        uploadList: newList,
      };
    },
  },
  INIT_STATE,
);
