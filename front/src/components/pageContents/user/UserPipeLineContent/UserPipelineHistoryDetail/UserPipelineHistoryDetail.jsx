import React, { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { useHistory, useLocation, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ReactFlowProvider } from '@xyflow/react';

import { getPipelineHistoryDetail } from '@src/apis/flightbase/pipeline';
import {
  handleReset,
  handleSetPipelineState,
} from '@src/store/modules/pipelineList';
import { STATUS_SUCCESS } from '@src/network';

import FlowHistoryComponent from './FlowHistoryComponent';

import { calRecordTime, convertBinaryByte } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserPipelineHistoryDetail.module.scss';

import BackIcon from '@src/static/images/icon/00-ic-basic-arrow-02-left.svg';

const cx = classNames.bind(style);

const calTransformList = (list) => {
  return list.map((info) => ({
    ...info,
    status: {
      status: 'none',
    },
  }));
};

const getPipelineHistoryDetailInfo = async (historyId, dispatch) => {
  const { result, message, status } = await getPipelineHistoryDetail(historyId);
  // done, stop일때 백엔드에서 보내주는 키값이 서로 다름(generation/_task). 옛 히스토리
  // 레코드(GenAI 레인 이전)는 신규 버킷이 없을 수 있어 ?? [] 방어.
  const transformGeneration = calTransformList(
    result.tasks.generation ?? result.tasks.generation_task ?? [],
  );
  const transformProcessTask = calTransformList(
    result.tasks.preprocessing ?? result.tasks.preprocessing_task ?? [],
  );
  const transformFinetuning = calTransformList(
    result.tasks.finetuning ?? result.tasks.finetuning_task ?? [],
  );
  const transformQuantize = calTransformList(
    result.tasks.quantize ?? result.tasks.quantize_task ?? [],
  );
  const transformLlmDeploy = calTransformList(
    result.tasks.llm_deploy ?? result.tasks.llm_deploy_task ?? [],
  );
  const transformPromptGen = calTransformList(
    result.tasks.prompt_gen ?? result.tasks.prompt_gen_task ?? [],
  );
  const transformDataGen = calTransformList(
    result.tasks.data_gen ?? result.tasks.data_gen_task ?? [],
  );
  const transformAlgoCall = calTransformList(
    result.tasks.algo_call ?? result.tasks.algo_call_task ?? [],
  );
  const transformProject = calTransformList(
    result.tasks.project ?? result.tasks.project_task ?? [],
  );
  const transformDeployment = calTransformList(
    result.tasks.deployment ?? result.tasks.deployment_task ?? [],
  );

  if (status === STATUS_SUCCESS) {
    dispatch(
      handleSetPipelineState({
        type: 'all',
        data: {
          generation_task: transformGeneration,
          preprocessing_task: transformProcessTask,
          finetuning_task: transformFinetuning,
          quantize_task: transformQuantize,
          llm_deploy_task: transformLlmDeploy,
          prompt_gen_task: transformPromptGen,
          data_gen_task: transformDataGen,
          algo_call_task: transformAlgoCall,
          project_task: transformProject,
          deployment_task: transformDeployment,
        },
      }),
    );
  } else {
    toast.error(message);
  }
};

const handleBackGo = (history, workspaceId, pipelineId) => {
  history.replace(`/user/workspace/${workspaceId}/pipeline/${pipelineId}`, {
    from: 'history',
  });
};

export default function UserPipelineHistoryDetail() {
  const history = useHistory();
  const dispatch = useDispatch();
  const location = useLocation();
  const { info } = location.state;

  const match = useRouteMatch();
  const { id: workspaceId, tid: pipelineId, did: historyId } = match.params;

  const diffTime = calRecordTime(info.start_datetime, info.end_datetime);

  useEffect(() => {
    getPipelineHistoryDetailInfo(historyId, dispatch);
    return () => dispatch(handleReset());
  }, [dispatch, historyId]);

  return (
    <div className={cx('header-cont')}>
      <div
        className={cx('back-btn')}
        onClick={() => handleBackGo(history, workspaceId, pipelineId)}
      >
        <img src={BackIcon} alt='back-icon' />
        <span>실행 기록</span>
      </div>
      <div className={cx('header-content-cont')}>
        <div className={cx('title-cont')}>
          <h2 className={cx('header-title')}>AI 파이프라인 무중단 실행</h2>
          <span className={cx('status-txt')}>{info.end_status}</span>
        </div>
      </div>
      <ul className={cx('info-list')}>
        <li className={cx('info-item')}>
          <span className={cx('label')}>자동 업데이트 설정</span>
          <span className={cx('value')}>
            {info.is_retraining_setting ? '설정' : '미설정'}
          </span>
        </li>
        <li className={cx('info-item')}>
          <span className={cx('label')}>재학습 횟수</span>
          <span className={cx('value')}>{info.retraining_count} 회</span>
        </li>
        <li className={cx('info-item')}>
          <span className={cx('label')}>데이터 증가량</span>
          <span className={cx('value')}>
            {convertBinaryByte(info.increase_dataset_size)}
          </span>
        </li>
        <li className={cx('info-item')}>
          <span className={cx('label')}>실행자</span>
          <span className={cx('value')}>{info.start_user_name}</span>
        </li>
        <li className={cx('info-item')}>
          <span className={cx('label')}>시작 기간</span>
          <span className={cx('value')}>{info.start_datetime ?? '-'}</span>
        </li>
        <li className={cx('info-item')}>
          <span className={cx('label')}>종료 기간</span>
          <span className={cx('value')}>{info.end_datetime ?? '-'}</span>
        </li>
        <li className={cx('info-item')}>
          <span className={cx('label')}>소요 기간</span>
          <span className={cx('value')}>{diffTime ?? '-'}</span>
        </li>
      </ul>
      <p className={cx('pipeline-title')}>파이프라인</p>
      <div className={cx('pipeline-cont')}>
        <ReactFlowProvider>
          <FlowHistoryComponent
            handleResetData={() => {}}
            isStopBtn={'history'}
          />
        </ReactFlowProvider>
      </div>
    </div>
  );
}
