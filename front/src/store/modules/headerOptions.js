import { createAction, handleActions } from 'redux-actions';

const WORKSPACE_POPUP = 'headerOptions/WORKSPACE_POPUP';
const USER_SETTING_POPUP = 'headerOptions/USER_SETTING_POPUP';
const LANG_SETTING_POPUP = 'headerOptions/LANG_SETTING_POPUP';
const SERVICE_PORTAL_POPUP = 'headerOptions/SERVICE_PORTAL_POPUP';
const CLOSE_HEADER_POPUP = 'headerOptions/CLOSE_HEADER_POPUP';
const ALARM_POPUP = 'headerOptions/ALARM_POPUP';

export const workspacePopup = createAction(WORKSPACE_POPUP);
export const userSettingPopup = createAction(USER_SETTING_POPUP);
export const alarmPopup = createAction(ALARM_POPUP);
export const langSettingPopup = createAction(LANG_SETTING_POPUP);
export const servicePortalPopup = createAction(SERVICE_PORTAL_POPUP);
export const closeHeaderPopup = createAction(CLOSE_HEADER_POPUP);

const initState = {
  workspacePopup: false,
  userSettingPopup: false,
  alarmPopup: false,
  langSettingPopup: false,
  servicePortalPopup: false,
};

export default handleActions(
  {
    [WORKSPACE_POPUP]: ({ workspacePopup }) => ({
      userSettingPopup: false,
      langSettingPopup: false,
      servicePortalPopup: false,
      workspacePopup: !workspacePopup,
      alarmPopup: false,
    }),
    [USER_SETTING_POPUP]: ({ userSettingPopup }) => ({
      workspacePopup: false,
      langSettingPopup: false,
      servicePortalPopup: false,
      userSettingPopup: !userSettingPopup,
      alarmPopup: false,
    }),
    [LANG_SETTING_POPUP]: ({ langSettingPopup }) => ({
      workspacePopup: false,
      servicePortalPopup: false,
      userSettingPopup: false,
      langSettingPopup: !langSettingPopup,
      alarmPopup: false,
    }),
    [SERVICE_PORTAL_POPUP]: ({ servicePortalPopup }) => ({
      workspacePopup: false,
      userSettingPopup: false,
      langSettingPopup: false,
      servicePortalPopup: !servicePortalPopup,
      alarmPopup: false,
    }),
    [ALARM_POPUP]: ({ alarmPopup }) => ({
      workspacePopup: false,
      userSettingPopup: false,
      langSettingPopup: false,
      servicePortalPopup: false,
      alarmPopup: !alarmPopup,
    }),
    [CLOSE_HEADER_POPUP]: () => initState,
  },
  initState,
);
