import { createAction, handleActions } from 'redux-actions';

const CHANGE_ALARM_CONDITION = 'alarm/CHANGE_ALARM_CONDITION';

export const actionUpdateAlarm = createAction(CHANGE_ALARM_CONDITION);

export const ALARM_TYPE = {
  workspace: 'workspace',
  user: 'user',
  project: 'project',
  deployment: 'deployment',
  resource: 'resource',
};

const INIT_STATE = {
  workspace: null,
  user: null,
  project: null,
  deployment: null,
  resource: null,
};

export default handleActions(
  {
    [CHANGE_ALARM_CONDITION]: (state, action) => {
      const { value: diffObjValue } = action.payload;
      const returnObj = {
        ...state,
      };

      for (const key in diffObjValue) {
        // 랜덤하게 ID 생성
        const generateRandomId = (key) => {
          return `${key}_${Math.random()
            .toString(36)
            .substring(2, 11)}_${Date.now()}`;
        };
        returnObj[key] = generateRandomId(key);
      }

      return returnObj;
    },
  },
  INIT_STATE,
);
