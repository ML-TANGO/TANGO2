import React, { memo } from 'react';

import CardFrame from './CardFrame';

import './ReactFlowComponent/ReactFlowComponent.scss';

const TtaskType = {
  preprocessing: 'pre',
  project: 'train',
  deployment: 'deployment',
};

const calCardType = (task_type) => {
  return TtaskType[task_type];
};

const calParameter = (parameter) => {
  if (typeof parameter === 'string') return parameter;
  if (parameter.length === 0) return '-';
  const transformList = parameter.map(({ key, value }) => `${key}: ${value}`);
  const joinValue = transformList.join(', ');
  return joinValue;
};

export default memo(({ data }) => {
  const {
    id,
    task_type,
    task_name,
    task_item_id,
    run_code,
    gpu_count,
    image_name,
    coordinate,
    parameter,
    handleResetData,
    status,
    task_item_tool_status,
    isStopBtn,
    task_item_type,
    pipelineType,
    built_in_params,
  } = data;

  const cardType = calCardType(task_type);
  const parameterValue = calParameter(parameter);

  return (
    <CardFrame
      id={id}
      isStopBtn={isStopBtn}
      status={status.status}
      task_item_tool_status={task_item_tool_status}
      task_name={task_name}
      cardType={cardType}
      gpuValue={gpu_count}
      coordinate={coordinate}
      dockerImageName={image_name}
      trainCodeName={run_code}
      parameter={parameterValue}
      task_item_id={task_item_id}
      task_item_type={task_item_type}
      pipelineType={pipelineType}
      built_in_params={built_in_params}
      handleResetData={handleResetData}
    />
  );
});
