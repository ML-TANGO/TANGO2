import { toast } from '@src/components/Toast';

import { getPipeline } from '@src/apis/flightbase/pipeline';
import { startPath } from '@src/store/modules/breadCrumb';
import { STATUS_SUCCESS } from '@src/network';

import {
  calFormatSecondToTime,
  calPlusNineHours,
  calSecondDifference,
} from '@src/utils';

export const breadCrumbHandler = (dispatch) => {
  dispatch(
    startPath([
      {
        component: {
          name: 'AIpipeline',
        },
      },
    ]),
  );
};

export const getPipelineMenu = async (workspaceId, setCardData) => {
  const res = await getPipeline(workspaceId);
  const { result, message, status } = res;
  if (status === STATUS_SUCCESS) {
    const copyList = result.slice();

    const transformList = copyList.map((cardInfo) => {
      const {
        id,
        name: title,
        description: subTitle,
        owner_name: constructor,
        create_datetime: createTime,
        start_datetime,
        end_datetime,
        access,
        bookmark,
        private_user_list,
      } = cardInfo;

      const diifSeconds = calSecondDifference(
        calPlusNineHours(start_datetime),
        end_datetime ? end_datetime : new Date(),
      );
      const runningTime = calFormatSecondToTime(diifSeconds);

      return {
        id,
        title,
        subTitle,
        createTime,
        constructor,
        runningTime: start_datetime ? runningTime : '-',
        constructorName: constructor,
        status: start_datetime && !end_datetime ? 'running' : 'stop',
        isAccess: access,
        isBookMark: bookmark,
        private_user_list,
      };
    });
    const sortList = transformList.sort((a, b) => b.isBookMark - a.isBookMark);
    setCardData(sortList);
  } else {
    toast.error(message);
  }
};
