import { handleActions, createAction } from 'redux-actions';

const OPEN_NAV = 'nav/OPEN_NAV';
const CLOSE_NAV = 'nav/CLOSE_NAV';

export const openNav = createAction(OPEN_NAV);
export const closeNav = createAction(CLOSE_NAV);

const INIT_STATE = {
  isExpand: true,
};

export default handleActions({
  [OPEN_NAV]: (state) => ({ ...state, isExpand: true }),
  [CLOSE_NAV]: (state) => ({ ...state, isExpand: false }),
}, INIT_STATE);
