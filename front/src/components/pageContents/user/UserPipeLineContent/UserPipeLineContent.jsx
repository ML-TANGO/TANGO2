import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useRouteMatch } from 'react-router-dom';

import { ReactFlowProvider } from '@xyflow/react';

import usePipelineData from './usePipelineData';
import usePipelineInfo from './usePipelineInfo';
import UserPipeLineInfo from './UserPipeLineInfo';
import UserPipeLineProject from './UserPipeLineProject';
import PipeLineProjectHeader from './UserPipeLineProject/PipeLineProjectHeader';
import UserPipeLineSetting from './UserPipeLineSetting';
import UserPipeLineTab from './UserPipeLineTab';

import classNames from 'classnames/bind';
import style from './UserPipeLineContent.module.scss';

const cx = classNames.bind(style);

export default function UserPipeLineContent() {
  const { t } = useTranslation();
  const location = useLocation();

  const match = useRouteMatch();
  const { params } = match;
  const { id: workspaceId, tid: pipelineId } = params;

  const [tab, setTab] = useState(0);
  const tabList = useMemo(() => {
    return [
      {
        label: t('information.label'),
        value: 0,
      },
      { label: t('setting.label'), value: 1 },
      { label: '실행 기록', value: 2 },
    ];
  }, [t]);
  const handleTab = useCallback((v) => {
    setTab(v);
  }, []);

  const { getPipelineInfo, datasetInfo, pipeline_info, restart_setting } =
    usePipelineInfo(pipelineId, tab);

  const {
    projectInfo,
    isStopBtn,
    headerInfoList,
    getPipelineData,
    handleDataset,
  } = usePipelineData(pipelineId, tab);
  const {
    pipeline_name,
    create_datetime,
    owner_name,
    create_user_name,
    description,
    dataset_info,
    retraining_config,
  } = projectInfo;

  useEffect(() => {
    if (!location.state) return;

    handleTab(2);
  }, [handleTab, location.state]);

  return (
    <div className={cx('pipeline-project-cont')}>
      <ReactFlowProvider>
        <PipeLineProjectHeader
          workspaceId={workspaceId}
          tab={tab}
          pipeline_name={
            pipeline_name === '-' ? pipeline_info.name : pipeline_name
          }
          create_datetime={create_datetime}
          owner_name={owner_name}
          create_user_name={create_user_name}
          description={description}
          datasetValue={dataset_info.id}
          retraining_config={tab === 1 ? retraining_config : restart_setting}
          isStopBtn={isStopBtn}
          handleResetData={tab === 0 ? getPipelineInfo : getPipelineData}
        />
        <UserPipeLineTab
          selectedTab={tab}
          tabList={tabList}
          handleTab={handleTab}
        />
        {tab === 0 && (
          <UserPipeLineInfo
            datasetInfo={datasetInfo}
            pipeline_info={pipeline_info}
            restart_setting={restart_setting}
          />
        )}
        {tab === 1 && (
          <UserPipeLineProject
            pipelineType={pipeline_info.type}
            projectInfo={projectInfo}
            headerInfoList={headerInfoList}
            isStopBtn={isStopBtn}
            getPipelineInfo={getPipelineData}
            handleDataset={handleDataset}
          />
        )}
        {tab === 2 && <UserPipeLineSetting />}
      </ReactFlowProvider>
    </div>
  );
}
