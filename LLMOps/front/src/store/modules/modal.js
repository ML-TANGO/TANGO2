import { createAction, handleActions } from 'redux-actions';

const OPEN_MODAL = 'modal/OPEN_MODAL';
const CLOSE_MODAL = 'modal/CLOSE_MODAL';
const CLOSE_ALL_MODAL = 'modal/CLOSE_ALL_MODAL';

export const openModal = createAction(OPEN_MODAL);
export const closeModal = createAction(CLOSE_MODAL);
export const closeAllModal = createAction(CLOSE_ALL_MODAL);

const INIT_STATE = {};

export default handleActions(
  {
    [OPEN_MODAL]: (state, { payload: { modalType, modalData = {} } }) => {
      return {
        ...state,
        [modalType]: modalData,
      };
    },
    [CLOSE_MODAL]: (state, { payload: modalType }) => {
      const newState = { ...state };
      delete newState[modalType];
      return newState;
    },
    [CLOSE_ALL_MODAL]: () => ({}),
  },
  INIT_STATE,
);
