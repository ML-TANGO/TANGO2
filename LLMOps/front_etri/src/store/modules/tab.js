
import { handleActions, createAction } from 'redux-actions';

const ACTIVE_TAB = 'tab/ACTIVE_TAB';
const INACTIVE_TAB = 'tab/INACTIVE_TAB';

export const activeTab = createAction(ACTIVE_TAB);
export const inActiveTab = createAction(INACTIVE_TAB);

const INIT_STATE = {
  isActive: true,
};

export default handleActions({
  [ACTIVE_TAB]: (state) => ({ ...state, isActive: true }),
  [INACTIVE_TAB]: (state) => ({ ...state, isActive: false }),
}, INIT_STATE);
