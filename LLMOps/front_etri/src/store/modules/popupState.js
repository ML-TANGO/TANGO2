import { createAction, handleActions } from 'redux-actions';

const OPEN_POPUP = 'popup/OPEN_POPUP';
const CLOSE_POPUP = 'popup/CLOSE_POPUP';

export const handleOpenPopup = createAction(OPEN_POPUP);
export const handleClosePopup = createAction(CLOSE_POPUP);

const initState = {
  isOpen: false,
  type: 'main',
  icon: null,
  isAnimation: false,
  frontTitle: '',
  popupTitle: '',
  popupContents: '',
  cancelBtnLabel: '취소',
  submitBtnLabel: '확인',
  handleCancel: () => {},
  handleSubmit: () => {},
  style: {},
};

export default handleActions(
  {
    [handleOpenPopup]: (state, action) => {
      const {
        type,
        icon,
        isAnimation,
        frontTitle,
        popupTitle,
        popupContents,
        cancelBtnLabel,
        submitBtnLabel,
        handleCancel,
        handleSubmit,
        style,
      } = action.payload;

      return {
        ...state,
        isOpen: true,
        type,
        icon,
        isAnimation,
        frontTitle,
        popupTitle,
        popupContents,
        cancelBtnLabel,
        submitBtnLabel,
        handleCancel,
        handleSubmit,
        style,
      };
    },
    [handleClosePopup]: () => initState,
  },
  initState,
);
