import { handleActions, createAction } from 'redux-actions';

const OPEN_PROGRESS_LIST = 'progrss/OPEN_PROGRESS_LIST';
const CLOSE_PROGRESS_LIST = 'progrss/CLOSE_PROGRESS_LIST';
const DELETE_PROGRESS_LIST = 'progrss/DELETE_PROGRESS_LIST';

export const openProgressList = createAction(OPEN_PROGRESS_LIST);
export const closeProgressList = createAction(CLOSE_PROGRESS_LIST);
export const deleteProgressList = createAction(DELETE_PROGRESS_LIST);

const INIT_STATE = {
  progressList: [],
  isOpen: false,
};

export default handleActions(
  {
    [OPEN_PROGRESS_LIST]: (state, { payload: progressList }) => ({
      isOpen: true,
      progressList: [...state.progressList, ...progressList],
    }),
    [CLOSE_PROGRESS_LIST]: () => ({
      isOpen: false,
      progressList: [],
    }),
    [DELETE_PROGRESS_LIST]: (state, { payload: name }) => {
      const { progressList, isOpen } = state;
      const newProgressList = [];
      let newOpenState = isOpen;

      progressList.forEach((instance) => {
        const { name: n } = instance;
        if (n !== name) {
          newProgressList.push(instance);
        }
      });

      if (newProgressList.length === 0) {
        newOpenState = false;
      }

      return {
        ...state,
        isOpen: newOpenState,
        progressList: newProgressList,
      };
    },
  },
  INIT_STATE,
);
