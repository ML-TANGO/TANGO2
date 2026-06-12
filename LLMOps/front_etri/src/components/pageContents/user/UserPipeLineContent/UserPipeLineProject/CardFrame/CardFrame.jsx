import React, { useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2, Tooltip } from '@tango/ui-react';

import { Handle, Position } from '@xyflow/react';

import { calTypeImg } from '@src/components/Modal/AddAiPipeLinepreprocessModal/AddAiPipeLinepreprocessModal';

import {
  deletePipelinesTask,
  putPipelinesDeleteRow,
} from '@src/apis/flightbase/pipeline';
import { closeModal, openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import { TRevertaskType } from '../ReactFlowComponent/util';

// CSS Module
import classNames from 'classnames/bind';
import style from './CardFrame.module.scss';

import IconArrow from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import IconLink from '@src/static/images/icon/ic-shortcut-gray.svg';

const cx = classNames.bind(style);

const calCardLabel = (cardType, t) => {
  if (cardType === 'pre') return '학습 데이터 전처리';
  if (cardType === 'train') return '학습';
  if (cardType === 'deployment') return '배포';
  return '-';
};

export const calPointerColor = (cardType) => {
  if (cardType === 'pre') return '#2D76F8';
  if (cardType === 'train') return '#FF7A00';
  return '#00C775';
};

const calLastTargetHandle = (cardType, deployMaxY, y_index) => {
  if (cardType !== 'deployment') return true;
  if (deployMaxY !== y_index) return true;
  return false;
};

const calTypetoTypeList = (
  cardType,
  preprocessing_task,
  project_task,
  deployment_task,
) => {
  if (cardType === 'pre') return preprocessing_task;
  if (cardType === 'train') return project_task;
  return deployment_task;
};

const calIsLastxIndex = (list, coordinate) => {
  const copyList = list.slice();
  const { y_index } = coordinate;
  const filterList = copyList.filter((el) => el.coordinate.y_index === y_index);
  if (filterList.length === 1) return true;
  return false;
};

const calStatusMessage = (status) => {
  if (status === 'running') return '작업 실행 중입니다.';
  if (['pending', 'installing'].includes(status)) return '작업 대기 중입니다.';
  if (status === 'done') return '작업 완료되었습니다.';
  return '';
};

const calStatuscolor = (status, isStopBtn) => {
  if (!isStopBtn && status === 'error') return '';
  if (!isStopBtn && status === 'done') return '';
  return status;
};

const calIsTrainTool = (isStopBtn, cardType, task_item_type) => {
  if (isStopBtn) return false;
  if (cardType === 'deployment') return false;
  if (task_item_type === 'advanced') return true;
  if (task_item_type === 'built-in') return true;
  return false;
};

const handleDelete = async (id, handleRowDelete, handleResetData) => {
  const { status, message } = await deletePipelinesTask(id);
  if (status !== STATUS_SUCCESS) {
    toast.error(message);
    return;
  }
  await handleRowDelete();
  await handleResetData();
};

const handleGoTrain = (history, workspaceId, task_item_id, cardType) => {
  if (cardType === 'pre') {
    history.push(
      `/user/workspace/${workspaceId}/datasets/process/${task_item_id}/detail`,
    );
  } else {
    history.push(
      `/user/workspace/${workspaceId}/trainings/${task_item_id}/workbench`,
    );
  }
};

const DeleteButton = ({
  id,
  borderColor,
  handleRowDelete,
  handleDelete,
  handleResetData,
}) => {
  return (
    <button
      className={cx('delete-btn')}
      style={{ boxShadow: `0px 3px 12px 0px ${borderColor}` }}
      onClick={() => handleDelete(id, handleRowDelete, handleResetData)}
    >
      <svg
        xmlns='http://www.w3.org/2000/svg'
        width='16'
        height='16'
        viewBox='0 0 16 16'
        fill='none'
      >
        <path
          d='M12.9701 3.97132C13.2305 3.71097 13.2305 3.28886 12.9701 3.02851C12.7098 2.76816 12.2876 2.76816 12.0273 3.02851L7.9987 7.05711L3.9701 3.02851C3.70975 2.76816 3.28764 2.76816 3.02729 3.02851C2.76694 3.28886 2.76694 3.71097 3.02729 3.97132L7.05589 7.99992L3.02729 12.0285C2.76694 12.2889 2.76694 12.711 3.02729 12.9713C3.28764 13.2317 3.70975 13.2317 3.9701 12.9713L7.9987 8.94273L12.0273 12.9713C12.2876 13.2317 12.7098 13.2317 12.9701 12.9713C13.2305 12.711 13.2305 12.2889 12.9701 12.0285L8.94151 7.99992L12.9701 3.97132Z'
          fill={borderColor}
        />
      </svg>
    </button>
  );
};

const AllmSvg = ({ color }) => {
  return (
    <svg
      width='16'
      height='17'
      viewBox='0 0 16 17'
      xmlns='http://www.w3.org/2000/svg'
    >
      <path
        d='M2.4 6.9c.884 0 1.6-.717 1.6-1.6 0-.884-.716-1.6-1.6-1.6S.8 4.415.8 5.3c0 .883.716 1.6 1.6 1.6Z'
        fill={color}
      />
      <path
        d='M2.4 13.3c.884 0 1.6-.716 1.6-1.6 0-.884-.716-1.6-1.6-1.6s-1.6.716-1.6 1.6c0 .884.716 1.6 1.6 1.6Z'
        fill={color}
      />
      <path
        d='M8.8 4.5c.884 0 1.6-.716 1.6-1.6 0-.884-.716-1.6-1.6-1.6s-1.6.716-1.6 1.6c0 .884.716 1.6 1.6 1.6Z'
        fill={color}
      />
      <path
        d='M8.8 10.1c.884 0 1.6-.716 1.6-1.6 0-.884-.716-1.6-1.6-1.6s-1.6.716-1.6 1.6c0 .884.716 1.6 1.6 1.6Z'
        fill={color}
      />
      <path
        d='M8.8 15.7c.884 0 1.6-.716 1.6-1.6 0-.884-.716-1.6-1.6-1.6s-1.6.716-1.6 1.6c0 .884.716 1.6 1.6 1.6Z'
        fill={color}
      />
      <path
        d='M13.6 10.1c.884 0 1.6-.716 1.6-1.6 0-.884-.716-1.6-1.6-1.6s-1.6.716-1.6 1.6c0 .884.716 1.6 1.6 1.6Z'
        fill={color}
      />
      <path
        d='M8.8 2.9l4.8 5.6-4.8 5.6M13.6 8.5H8.8'
        stroke={color}
        strokeMiterlimit='10'
      />
      <path
        d='M2.4 11.7l6.4-8.8-6.4 2.4 6.4 8.8-6.4-2.4ZM2.4 11.7l6.4-3.2'
        stroke={color}
        strokeMiterlimit='10'
        strokeLinejoin='bevel'
      />
      <path d='M2.333 5.168l6.467 3.333' stroke={color} strokeMiterlimit='10' />
    </svg>
  );
};

const calTypeIcon = (cardType, task_item_type, status, isStopBtn) => {
  if (task_item_type === 'advanced') {
    if (isStopBtn) {
      if (status === 'error') return <AllmSvg color='#ff0000' />;
      if (status === 'done') return <AllmSvg color='#c1c1c1' />;
    }
    const color = calPointerColor(cardType);
    return <AllmSvg color={color} />;
  }
  const imgPath = calTypeImg(task_item_type);
  return (
    <img className={cx('type-img')} src={imgPath} alt='데이터 타입 이미지' />
  );
};

export default function CardFrame({
  id,
  isStopBtn,
  task_name,
  cardType,
  gpuValue,
  coordinate,
  dockerImageName,
  trainCodeName,
  task_item_id,
  parameter,
  task_item_tool_status,
  task_item_type,
  pipelineType,
  status = '',
  built_in_params,
  handleResetData,
}) {
  const match = useRouteMatch();
  const { params } = match;
  const { id: workspaceId, tid: pipelineId } = params;

  const history = useHistory();
  const dispatch = useDispatch();

  const { preprocessing_task, project_task, deployment_task } = useSelector(
    (state) => state.pipelineList,
    shallowEqual,
  );
  const { y_index } = coordinate;
  const imgIcon = calTypeIcon(cardType, task_item_type, status, isStopBtn);

  const myList = calTypetoTypeList(
    cardType,
    preprocessing_task,
    project_task,
    deployment_task,
  );
  const isLastXindex = calIsLastxIndex(myList, coordinate);

  const deployYlist = deployment_task.map((el) => el.coordinate.y_index);
  const deployMaxY = Math.max(...deployYlist);

  const isLastHandle = calLastTargetHandle(cardType, deployMaxY, y_index);

  const headerLabel = calCardLabel(cardType);
  const borderColor = calPointerColor(cardType);

  const [isOpen, setIsOpen] = useState(isStopBtn === 'history' ? true : false);
  const [isHover, setHover] = useState(false);

  const statusMessage = calStatusMessage(status);
  const statusColor = calStatuscolor(status, isStopBtn);
  const logtitleValue = status === 'running' ? '실행 로그' : '결과 로그';
  const isTrainTool = calIsTrainTool(isStopBtn, cardType, task_item_type);

  const handleRowDelete = async () => {
    if (isLastXindex) {
      const { status, message } = await putPipelinesDeleteRow({
        pipeline_id: pipelineId,
        task_type: TRevertaskType[cardType],
        y_index_base: y_index,
      });

      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      }
    }
  };

  const handleModal = (dispatch, logtitleValue, task_name, cardType, id) => {
    dispatch(
      openModal({
        modalType: 'AI_PIPELINE_LOG',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('AI_PIPELINE_LOG'));
            },
          },
          title: logtitleValue,
          taskName: task_name,
          taskType: cardType,
          taskId: id,
        },
      }),
    );
  };

  return (
    <div
      className={cx('card-cont', cardType, statusColor)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className={cx('card-header-cont', cardType, statusColor)}>
        <div className={cx('type-cont')}>
          {imgIcon}
          <span
            className={cx(
              'card-title',
              cardType,
              isStopBtn && ['done', 'pending'].includes(status) && 'done',
              isStopBtn && status === 'error' && 'error',
            )}
          >
            {headerLabel}
          </span>
          {isStopBtn && status === 'error' && (
            <img
              className={cx('error-icon')}
              src='/src/static/images/icon/ic-warning-yellow.svg'
              alt='error-icon'
            />
          )}
        </div>
        {isStopBtn !== 'history' && (
          <img
            className={cx('arrow-img', isOpen && 'open')}
            src={IconArrow}
            alt='arrow-img'
            onClick={() => setIsOpen((prev) => !prev)}
          />
        )}
        {!isStopBtn && pipelineType !== 'built-in' && (
          <DeleteButton
            id={id}
            borderColor={borderColor}
            handleRowDelete={handleRowDelete}
            handleDelete={handleDelete}
            handleResetData={handleResetData}
          />
        )}
      </div>
      <div className={cx('card-body-cont')}>
        <div className={cx('body-top-cont')}>
          <div className={cx('name-cont')}>
            <span className={cx('name-txt')}>{task_name}</span>
            {isStopBtn && status && (
              <span className={cx('status-txt', status)}>{statusMessage}</span>
            )}
          </div>
          {status !== 'error' && isStopBtn && isStopBtn !== 'history' && (
            <div className={cx('log-btn-cont')}>
              <ButtonV2
                label={logtitleValue}
                colorType='skyblue'
                onClick={() =>
                  handleModal(dispatch, logtitleValue, task_name, cardType, id)
                }
                disabled={['installing', 'pending'].includes(status)}
              />
            </div>
          )}
          {!isStopBtn && cardType !== 'pre' && (
            <div className={cx('gpu-cont')}>
              <span className={cx('gpu-label')}>GPU 할당</span>
              <span className={cx('gpu-value')}>{gpuValue}</span>
              {gpuValue > 1 && (
                <span className={cx('multi-gpu-value')}>
                  1-GPU 서버 x{gpuValue}
                </span>
              )}
            </div>
          )}
          {isTrainTool && task_item_type === 'advanced' && (
            <div>
              <div className={cx('tool-cont')}>
                <span className={cx('gray-font')}>개발도구</span>
                <img
                  src={IconLink}
                  alt='link-img'
                  onClick={() =>
                    handleGoTrain(history, workspaceId, task_item_id, cardType)
                  }
                />
              </div>
              {!task_item_tool_status && (
                <p className={cx('tool-message')}>
                  현재 실행중인 개발도구가 없습니다.
                </p>
              )}
            </div>
          )}
        </div>
        {isOpen && (
          <div className={cx('body-bottom-cont')}>
            <div className={cx('border')}></div>
            {isStopBtn && cardType !== 'pre' && (
              <div className={cx('gpu-cont')}>
                <span className={cx('gpu-label')}>GPU 할당</span>
                <span className={cx('gpu-value')}>{gpuValue}</span>
                {gpuValue > 1 && (
                  <span className={cx('multi-gpu-value')}>
                    1-GPU 서버 x{gpuValue}
                  </span>
                )}
              </div>
            )}
            {dockerImageName && (
              <span className={cx('dark-font')}>{dockerImageName ?? '-'}</span>
            )}
            {trainCodeName && (
              <span className={cx('dark-font')}>{trainCodeName ?? '-'}</span>
            )}
            {parameter && (
              <span className={cx('dark-font')}>{parameter ?? '-'}</span>
            )}
            {built_in_params.length > 0 && (
              <div>
                <span>Built-in Params</span>
                <Tooltip
                  icon='/src/static/images/icon/00-ic-alert-info-o.svg'
                  iconCustomStyle={{
                    width: '16px',
                    height: '16px',
                    marginLeft: '8px',
                    paddingBottom: '2px',
                  }}
                  contents={built_in_params.map((el) => (
                    <div className={cx('built-in-params-cont')}>
                      <span className={cx('dark-font')}>
                        {el.key}: {el.value ?? '-'}
                      </span>
                    </div>
                  ))}
                  contentsAlign={{ vertical: 'top' }}
                  contentsCustomStyle={{
                    width: '300px',
                    padding: '24px',
                    borderRadius: '10px',
                    border: '0.5px solid #DEE9FF',
                    background: '#FFF',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>
      {(cardType !== 'pre' || y_index !== 0) && (
        <Handle
          type='target'
          position={Position.Top}
          id={`${cardType}-${id}-top`}
          style={{
            width: '16px',
            height: '16px',
            background: '#fff',
            border: `1px solid ${borderColor}`,
            opacity:
              !isStopBtn && isHover && pipelineType !== 'built-in' ? 1 : 0,
          }}
          isConnectable={true}
        />
      )}
      {isLastHandle && (
        <Handle
          type='source'
          position={Position.Bottom}
          id={`${cardType}-${id}-bottom`}
          style={{
            width: '16px',
            height: '16px',
            background: '#fff',
            border: `1px solid ${borderColor}`,
            opacity:
              !isStopBtn && isHover && pipelineType !== 'built-in' ? 1 : 0,

            filter: 'drop-shadow(0px 3px 12px rgba(45, 118, 248, 0.40))',
          }}
          isConnectable={true}
        />
      )}
    </div>
  );
}
