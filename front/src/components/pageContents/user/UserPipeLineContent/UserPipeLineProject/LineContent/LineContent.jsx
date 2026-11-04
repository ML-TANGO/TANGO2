import React from 'react';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import { handleAddData } from '../ReactFlowComponent/util';

// CSS Module
import classNames from 'classnames/bind';
import style from './LineContent.module.scss';

const cx = classNames.bind(style);

export default function LineContent({ data }) {
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const { params } = match;
  const { id: workspaceId, tid: pipelineId } = params;

  const { x, y, type, handleResetData, isStopBtn, dataset_info, pipelineType } =
    data;

  return (
    <div className={cx('content-cont')}>
      <div className={cx('btn-cont')}>
        {!isStopBtn && (
          <ButtonV2
            colorType='skyblue'
            label={
              <div className={cx('btn-label-cont')}>
                <span className={cx('plus-txt')}>+</span>
                <span className={cx('label-txt')}>병렬 작업 추가</span>
              </div>
            }
            onClick={() => {
              if (!dataset_info.id) {
                toast.error('학습 데이터셋을 선택해 주세요.');
                return;
              }
              handleAddData(
                dispatch,
                workspaceId,
                pipelineId,
                x,
                y,
                type,
                handleResetData,
                false,
                dataset_info,
              );
            }}
            style={{ padding: '10px 20px 10px 16px' }}
            disabled={pipelineType === 'built-in'}
          />
        )}
        {!isStopBtn && (
          <ButtonV2
            colorType='blue'
            label={
              <div className={cx('btn-label-cont')}>
                <span className={cx('plus-txt', 'deep')}>+</span>
                <span className={cx('label-txt', 'deep')}>직렬 작업 추가</span>
              </div>
            }
            onClick={() => {
              if (!dataset_info.id) {
                toast.error('학습 데이터셋을 선택해 주세요.');
                return;
              }
              handleAddData(
                dispatch,
                workspaceId,
                pipelineId,
                0,
                y + 1,
                type,
                handleResetData,
                true,
                dataset_info,
              );
            }}
            style={{
              backgroundColor: '#93BAFF',
              padding: '10px 20px 10px 16px',
            }}
            disabled={pipelineType === 'built-in'}
          />
        )}
      </div>
      {!isStopBtn && <div className={cx('dot-line')} />}
    </div>
  );
}
