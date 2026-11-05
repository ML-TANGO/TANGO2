import _ from 'lodash';
import { createAction, handleActions } from 'redux-actions';

const OPEN_POPUP = 'popup/OPEN_POPUP';
const CLOSE_POPUP = 'popup/CLOSE_POPUP';
const CLOSE_POPUP_ALL = 'popup/CLOSE_ALL';

export const openPopup = createAction(OPEN_POPUP);
export const closePopup = createAction(CLOSE_POPUP);
export const closePopupAll = createAction(CLOSE_POPUP_ALL);

const initState = {};

export default handleActions(
  {
    [OPEN_POPUP]: (state, { payload: type }) => {
      let newState = _.cloneDeep(state);
      Object.keys(newState).forEach((k) => {
        newState[k] = false;
      });
      newState[type] = true;

      return newState;
    },
    [CLOSE_POPUP]: (state, { payload: type }) => ({
      ...state,
      [type]: false,
    }),
    [CLOSE_POPUP_ALL]: () => {
      return {};
    },
  },
  initState,
);
