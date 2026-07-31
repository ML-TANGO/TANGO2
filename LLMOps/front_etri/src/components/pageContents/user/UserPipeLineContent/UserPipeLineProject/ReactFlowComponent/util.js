import { openModal } from '@src/store/modules/modal';

export const nodeLineColorStyle = {
  preprocessing: '#2D76F8',
  project: '#FF7A00',
  deployment_task: '#00C775',
};

export const TRevertaskType = {
  pre: 'preprocessing',
  train: 'project',
  deployment: 'deployment',
};

export const xPositionList = [
  0, 288, 576, 864, 1152, 1440, 1728, 2016, 2304, 2592,
];
export const typePosition = {
  preprocessing: {
    x: 0,
    y: 24,
    width: 288,
    height: 0,
  },
  project: {
    x: 0,
    y: 24,
    width: 288,
    height: 0,
  },
  deployment: {
    x: 0,
    y: 24,
    width: 288,
    height: 0,
  },
};

const calModalName = (type) => {
  // return 'ADD_PREPROCESS_BUILT_IN'; // 데이터 전처리 작업 Built-in 추가
  if (type === 'pre') return 'ADD_PREPREOCESS_DATA';
  // return 'ADD_TRAINING_BUILT_IN'; // 학습 작업 Built-in 추가
  if (type === 'train') return 'AI_TRAINING_SETTING';
  return 'ADD_DEPLOY_DATA';
};

export const handleAddData = (
  dispatch,
  workspaceId,
  pipelineId,
  x,
  y,
  type,
  handleResetData,
  isSerial,
  dataset_info,
) => {
  const modalType = calModalName(type);

  dispatch(
    openModal({
      modalType,
      modalData: {
        workspaceId,
        pipelineId,
        x_index: x,
        y_index: y,
        handleResetData,
        isSerial,
        dataset_info,
      },
    }),
  );
};

const subTitleObj = {
  '학습 데이터 전처리': 'header0',
  학습: 'header1',
  배포: 'header2',
};

export const calListHeaderGroup = (lastPositionY, subTitle, isStopBtn) => {
  const trainListHeaderGroup = {
    id: subTitleObj[subTitle],
    type: 'nodeHeader',
    data: {
      subTitle,
      isStopBtn,
    },
    position: {
      x: 0,
      y: lastPositionY,
    },
    style: {
      width: '100%',
    },
    draggable: false,
    connectable: false,
  };
  return trainListHeaderGroup;
};

export const calSwapArrayCoordinate = (arr, index1, index2) => {
  const copyArr = arr.slice();

  const coordinateX1 = copyArr[index1].data.coordinate.x_index;
  const coordinateX2 = copyArr[index2].data.coordinate.x_index;

  copyArr[index1].data.coordinate.x_index = coordinateX2;
  copyArr[index2].data.coordinate.x_index = coordinateX1;

  copyArr[index1].position.x = xPositionList[coordinateX2];
  copyArr[index1].position.y = 24;

  copyArr[index2].position.x = xPositionList[coordinateX1];
  copyArr[index2].position.y = 24;

  return copyArr;
};

export const calLastPosition = (lastValue) => {
  const lastType = lastValue.type;
  if (lastType === 'emptyGroup') {
    const startPosition = lastValue.position.y + 84;
    return startPosition;
  }
  return lastValue.position.y + 390 + 24;
};

export const calPreDataGroupList = (
  copyPreDataList,
  handleResetData,
  isStopBtn,
  dataset_info,
  pipelineType,
) => {
  const returnList = [];

  if (copyPreDataList.length === 0) {
    returnList.push({
      id: 'pre-group0',
      type: 'emptyGroup',
      data: {
        x: 0,
        y: 0,
        type: 'pre',
        handleResetData,
        isStopBtn,
        dataset_info,
        pipelineType,
      },
      position: {
        x: 0,
        y: 60,
      },
      style: {
        width: '100%',
        height: '84px',
      },
      draggable: false,
      connectable: false,
    });
    return returnList;
  }

  const yList = copyPreDataList.map((el) => el.coordinate.y_index);
  const maxY = Math.max(...yList);

  for (let i = 0; i < maxY + 1; i++) {
    const filterList = copyPreDataList.filter(
      (el) => el.coordinate.y_index === i,
    );
    const xList = filterList.map((el) => el.coordinate.x_index);
    const sortXList = xList.sort((a, b) => a - b);
    const xIndex = sortXList.findIndex((number, idx) => number !== idx);

    returnList.push({
      id: `pre-group${i + 1}`,
      type: 'lineGroup',
      data: {
        x: xIndex !== -1 ? xIndex : sortXList.length,
        y: i,
        type: 'pre',
        handleResetData,
        isStopBtn,
        dataset_info,
        pipelineType,
      },
      position: {
        x: 0,
        y: 44 + 390 * i,
      },
      style: {
        width: '100%',
        height: '390px',
      },
      draggable: false,
      connectable: false,
    });
  }
  return returnList;
};

export const calTrainGroupList = (
  list,
  handleResetData,
  trainStartPositionY,
  isStopBtn,
  dataset_info,
  pipelineType,
) => {
  const returnList = [];

  if (list.length === 0) {
    returnList.push({
      id: 'train-group0',
      type: 'emptyGroup',
      data: {
        x: 0,
        y: 0,
        type: 'train',
        handleResetData,
        isStopBtn,
        dataset_info,
        pipelineType,
      },
      position: {
        x: 0,
        y: trainStartPositionY + 60,
      },
      style: {
        width: '100%',
        height: '390px',
      },
      draggable: false,
      connectable: false,
    });
  }

  const yList = list.map((el) => el.coordinate.y_index);
  const maxY = Math.max(...yList);

  for (let i = 0; i < maxY + 1; i++) {
    const filterList = list.filter((el) => el.coordinate.y_index === i);
    const xList = filterList.map((el) => el.coordinate.x_index);
    const sortXList = xList.sort((a, b) => a - b);
    const xIndex = sortXList.findIndex((number, idx) => number !== idx);

    returnList.push({
      id: `train-group${i + 1}`,
      type: 'lineGroup',
      data: {
        x: xIndex !== -1 ? xIndex : sortXList.length,
        y: i,
        type: 'train',
        handleResetData,
        isStopBtn,
        dataset_info,
        pipelineType,
      },
      position: {
        x: 0,
        y: trainStartPositionY + 44 + 390 * i,
      },
      style: {
        width: '100%',
        height: '390px',
      },
      draggable: false,
      connectable: false,
    });
  }
  return returnList;
};

export const calDeloymentGroupList = (
  list,
  handleResetData,
  deploymentPositionY,
  isStopBtn,
  dataset_info,
  pipelineType,
) => {
  const returnList = [];
  if (list.length === 0) {
    returnList.push({
      id: 'deployment-group0',
      type: 'emptyGroup',
      data: {
        x: 0,
        y: 0,
        type: 'deploy',
        handleResetData,
        isStopBtn,
        dataset_info,
        pipelineType,
      },
      position: {
        x: 0,
        y: deploymentPositionY + 60,
      },
      style: {
        width: '100%',
        height: '84px',
      },
      draggable: false,
      connectable: false,
    });
    return returnList;
  }

  const yList = list.map((el) => el.coordinate.y_index);
  const maxY = Math.max(...yList);

  for (let i = 0; i < maxY + 1; i++) {
    const filterList = list.filter((el) => el.coordinate.y_index === i);
    const xList = filterList.map((el) => el.coordinate.x_index);
    const sortXList = xList.sort((a, b) => a - b);
    const xIndex = sortXList.findIndex((number, idx) => number !== idx);

    returnList.push({
      id: `deployment-group${i + 1}`,
      type: 'lineGroup',
      data: {
        x: xIndex !== -1 ? xIndex : sortXList.length,
        y: i,
        type: 'deploy',
        handleResetData,
        isStopBtn,
        dataset_info,
        pipelineType,
      },
      position: {
        x: 0,
        y: deploymentPositionY + 44 + 390 * i,
      },
      style: {
        width: '100%',
        height: '390px',
      },
      draggable: false,
      connectable: false,
    });
  }

  return returnList;
};

export const calDataNodeList = (
  list,
  groupType,
  handleResetData,
  isStopBtn,
  dataset_info,
  pipelineType,
) => {
  if (list.length === 0) return [];
  const returnList = list.map((info) => {
    const { id, coordinate, task_type } = info;
    const { x_index, y_index } = coordinate;

    return {
      id: `${id}`,
      type: 'node',
      data: { ...info, handleResetData, isStopBtn, dataset_info, pipelineType },
      position: {
        x: typePosition[task_type].x + typePosition[task_type].width * x_index,
        y: typePosition[task_type].y + typePosition[task_type].height * y_index,
      },
      style: {
        padding: 0,
        border: 'none',
        borderRadius: '16px',
      },
      connectable: true,
      parentId: `${groupType}${y_index + 1}`,
      extent: 'parent',
    };
  });
  return returnList;
};

export const calNodeDataList = (
  copyPreDataList,
  groupType,
  handleResetData,
  isStopBtn,
  dataset_info,
  pipelineType,
) => {
  const preDataListNodeList = calDataNodeList(
    copyPreDataList,
    groupType,
    handleResetData,
    isStopBtn,
    dataset_info,
    pipelineType,
  );
  return preDataListNodeList;
};

export const calHeight = (list) => {
  const copyGroupList = list.slice();
  const positionYList = copyGroupList.map((el) => {
    return el.position.y;
  });
  const maxHeight = Math.max(...positionYList);
  return maxHeight;
};

export const calLineColor = (isStopBtn, status, task_type) => {
  if (!isStopBtn) return '#2D76F8';
  if (status === 'done') return '#C1C1C1';
  const nodeLineColor = nodeLineColorStyle[task_type];
  return nodeLineColor;
};

export const calBorderAnimate = (status, isStopBtn) => {
  if (!isStopBtn) return false;
  if (status.status !== 'running') return false;
  return true;
};
