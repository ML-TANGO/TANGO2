import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2, Tooltip } from '@jonathan/ui-react';

import { useEdges, useNodes, useNodesState } from '@xyflow/react';

import {
  postPipelineRun,
  postPipelineStop,
} from '@src/apis/flightbase/pipeline';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './PipeLineProjectHeader.module.scss';

import BackIcon from '@src/static/images/icon/00-ic-basic-arrow-02-left.svg';

const cx = classNames.bind(style);

// GenAI 통합 파이프라인 레인 순서(생성 → 전처리 → 파인튜닝 → 양자화 → LLM배포).
// 마지막(터미널) 레인 = 노드가 존재하는 가장 뒤 레인. calIsConnect 연결성 판정에 사용.
const LANE_ORDER = [
  'generation',
  'preprocessing',
  'finetuning',
  'quantize',
  'llm_deploy',
];

const calErrorMessage = (taskCount, datasetValue, isConnect) => {
  if (!datasetValue) return '학습 데이터셋을 추가해주세요.';
  if (taskCount === 0) return '작업을 추가해 주세요.';
  if (!isConnect) return '커넥터를 추가해 주세요.';
  return '';
};

const calHeaderMessage = (isStopBtn, errorMessage) => {
  if (isStopBtn) return '파이프라인이 실행되고 있습니다.';
  return errorMessage;
};

const handleBackGo = (history, workspaceId) => {
  history.replace(`/user/workspace/${workspaceId}/pipeline`);
};

const handleSetting = (
  dispatch,
  pipelineId,
  retraining_config,
  handleResetData,
) => {
  dispatch(
    openModal({
      modalType: 'AI_DEPLOY_SETTING',
      modalData: {
        pipelineId: +pipelineId,
        retraining_config,
        handleResetData,
      },
    }),
  );
};

export const handleRun = async (pipelineId, handleResetData) => {
  const { status, message } = await postPipelineRun(pipelineId);
  if (status !== STATUS_SUCCESS) {
    toast.error(message);
  } else {
    await handleResetData();
  }
};

const handleSubmit = async (
  isStopBtn,
  pipelineId,
  handleResetData,
  isLoading,
  setIsLoading,
) => {
  if (isLoading) return;
  setIsLoading(true);
  if (isStopBtn) {
    await postPipelineStop(pipelineId);
  } else {
    await handleRun(pipelineId, handleResetData);
  }
  setIsLoading(false);
};

const PipeLineProjectHeader = React.memo(
  ({
    workspaceId,
    tab,
    pipeline_name,
    create_datetime,
    create_user_name,
    description,
    owner_name,
    datasetValue,
    retraining_config,
    isStopBtn,
    handleResetData,
  }) => {
    const { t } = useTranslation();
    const history = useHistory();
    const dispatch = useDispatch();
    const [isLoading, setIsLoading] = useState(false);

    const match = useRouteMatch();
    const { params } = match;
    const { tid: pipelineId } = params;

    const {
      generation_task,
      preprocessing_task,
      finetuning_task,
      quantize_task,
      llm_deploy_task,
    } = useSelector((state) => state.pipelineList, shallowEqual);

    const taskCount =
      generation_task.length +
      preprocessing_task.length +
      finetuning_task.length +
      quantize_task.length +
      llm_deploy_task.length;

    const nodes = useNodes();
    const edges = useEdges();

    const calFilterTypeNode = (nodes, isStopBtn) => {
      if (!nodes) return [[], []];
      if (nodes.length === 0) return [[], []];
      if (isStopBtn) return [[], []];

      return nodes.filter((item) => item.type === 'node');
    };

    const filterNodeList = calFilterTypeNode(nodes, isStopBtn);

    const calIsConnect = (filterNodeList, edges, isStopBtn) => {
      if (filterNodeList.length === 0) return false;
      if (isStopBtn) return true;
      if (filterNodeList.length === 1) return true; // 단일 노드 = 커넥터 불필요
      if (edges.length < filterNodeList.length - 1) return false;

      const edgeSourceMap = new Map();
      const edgeTargetMap = new Map();

      edges.forEach((item) => {
        edgeSourceMap.set(item.source, true);
        edgeTargetMap.set(item.target, true);
      });

      // 터미널 레인 = 노드가 존재하는 가장 뒤 레인(LANE_ORDER). 터미널=수신 필요, 그 외=송신 필요.
      const maxLane = Math.max(
        ...filterNodeList.map((node) =>
          LANE_ORDER.indexOf(node.data.task_type),
        ),
      );

      for (const filterNode of filterNodeList) {
        const laneIdx = LANE_ORDER.indexOf(filterNode.data.task_type);
        if (laneIdx === maxLane) {
          if (!edgeTargetMap.has(filterNode.id)) return false;
        } else {
          if (!edgeSourceMap.has(filterNode.id)) return false;
        }
      }

      return true;
    };

    const isConnect = calIsConnect(filterNodeList, edges, isStopBtn);
    const errorMessage = calErrorMessage(taskCount, datasetValue, isConnect);
    const isRunBtn = !!errorMessage;
    const headerMessage = calHeaderMessage(isStopBtn, errorMessage);

    return (
      <div className={cx('header-cont')}>
        <div
          className={cx('back-btn')}
          onClick={() => handleBackGo(history, workspaceId)}
        >
          <img src={BackIcon} alt='back-icon' />
          <span>AI 파이프라인</span>
        </div>
        <div className={cx('header-content-cont')}>
          <div className={cx('title-cont')}>
            <h2 className={cx('header-title')}>{pipeline_name}</h2>
            {tab === 1 && (
              <Tooltip
                customStyle={{ marginLeft: '8px' }}
                contents={
                  <div className={cx('tooltip-cont')}>
                    <p className={cx('project-name-txt')}>{pipeline_name}</p>
                    <span className={cx('create-time-txt')}>
                      {create_datetime}
                    </span>
                    <div className={cx('owner-cont')}>
                      <div className={cx('label-cont')}>
                        <span className={cx('label-txt')}>
                          {t('creator.label')}
                        </span>
                        <span className={cx('value-txt')}>
                          {create_user_name}
                        </span>
                      </div>
                      <div className={cx('label-cont')}>
                        <span className={cx('label-txt')}>
                          {t('owner.label')}
                        </span>
                        <span className={cx('value-txt')}>{owner_name}</span>
                      </div>
                    </div>
                    <div className={cx('border')}></div>
                    <div className={cx('desc-cont')}>
                      <span className={cx('label-txt')}>
                        {t('projectDescription.label')}
                      </span>
                      <span className={cx('value-txt')}>{description}</span>
                    </div>
                  </div>
                }
                contentsCustomStyle={{
                  border: '0.5px solid #DEE9FF',
                  borderRadius: '10px',
                  boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                  padding: '24px',
                }}
              />
            )}
          </div>
          <div className={cx('header-content-right')}>
            {tab === 1 && (
              <p className={cx('error-message-paragraph', isStopBtn && 'blue')}>
                {headerMessage}
              </p>
            )}
            {tab !== 2 && (
              <ButtonV2
                colorType='skyblue'
                label={'자동 업데이트 설정'}
                onClick={() =>
                  handleSetting(
                    dispatch,
                    pipelineId,
                    retraining_config,
                    handleResetData,
                  )
                }
              />
            )}
            {tab === 1 && (
              <ButtonV2
                label={t(isStopBtn ? 'stop.label' : 'run.label')}
                colorType={isStopBtn ? 'red' : 'blue'}
                onClick={() =>
                  handleSubmit(
                    isStopBtn,
                    pipelineId,
                    handleResetData,
                    isLoading,
                    setIsLoading,
                  )
                }
                isLoading={isLoading}
                disabled={isRunBtn}
              />
            )}
          </div>
        </div>
      </div>
    );
  },
);

export default PipeLineProjectHeader;
