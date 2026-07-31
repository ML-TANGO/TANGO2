import { handleActions, createAction } from 'redux-actions';

const OPEN_CONFIRM = 'confirm/OPEN_CONFIRM';
const CLOSE_CONFIRM = 'confirm/CLOSE_CONFIRM';

export const openConfirm = createAction(OPEN_CONFIRM);
export const closeConfirm = createAction(CLOSE_CONFIRM);

const initState = {
  isOpen: false,
  confirmData: {},
};

export default handleActions(
  {
    [openConfirm]: (state, action) => ({
      ...state,
      isOpen: true,
      confirmData: action.payload,
    }),
    [closeConfirm]: () => initState,
  },
  initState,
);
