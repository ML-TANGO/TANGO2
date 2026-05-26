import React, { useEffect, useState } from 'react';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { getTrainDatasetList } from '@src/apis/flightbase/pipeline';
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import Dataset from './Dataset';
import PipelineInfoHeader from './PipelineInfoHeader';
import ReactFlowComponent from './ReactFlowComponent';

import classNames from 'classnames/bind';
import style from './UserPipeLineProject.module.scss';

const cx = classNames.bind(style);

const getPipelineDatasetList = async (setDatasetList, workspaceId) => {
  const { result, status, message } = await getTrainDatasetList(workspaceId);
  if (status === STATUS_SUCCESS) {
    const resultTransform = result.map((el) => ({
      ...el,
      label: el.name,
      value: el.id,
    }));

    setDatasetList(resultTransform);
  } else {
    toast.error(message);
  }
};

export default function UserPipeLineProject({
  pipelineType,
  projectInfo,
  isStopBtn,
  headerInfoList,
  getPipelineInfo,
  handleDataset,
}) {
  const match = useRouteMatch();
  const { params } = match;
  const { id: workspaceId } = params;

  const {
    dataset_info,
    retraining_config,
    start_datetime,
    retraining_wait_start_time,
  } = projectInfo;

  const [datasetList, setDatasetList] = useState([]);

  useEffect(() => {
    getPipelineDatasetList(setDatasetList, workspaceId);

    loadModalComponent('AI_DEPLOY_SETTING');
    loadModalComponent('AI_TRAINING_SETTING');
    loadModalComponent('ADD_PREPREOCESS_DATA');
    loadModalComponent('ADD_DEPLOY_DATA');
  }, [workspaceId]);

  return (
    <div className={cx('pipeline-project-cont')}>
      {start_datetime && (
        <PipelineInfoHeader
          list={headerInfoList}
          retraining_config={retraining_config}
          retraining_wait_start_time={retraining_wait_start_time}
          isStopBtn={isStopBtn}
          handleResetData={getPipelineInfo}
        />
      )}
      <Dataset
        isStopBtn={isStopBtn}
        datasetOptions={datasetList}
        dataset_info={dataset_info}
        handleDataset={handleDataset}
        pipelineType={pipelineType}
      />
      <ReactFlowComponent
        pipelineType={pipelineType}
        handleResetData={getPipelineInfo}
        isStopBtn={isStopBtn}
        dataset_info={dataset_info}
      />
    </div>
  );
}
