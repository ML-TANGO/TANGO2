import React from 'react';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import { handleAddData } from '../ReactFlowComponent/util';

// CSS Module
import classNames from 'classnames/bind';
import style from './EmptyContent.module.scss';

const cx = classNames.bind(style);

const calBtnLabel = (type) => {
  if (type === 'generate') return '생성 작업 추가';
  if (type === 'pre') return '데이터 전처리 작업 추가';
  if (type === 'train') return '학습 작업 추가';
  if (type === 'finetune') return '파인튜닝 작업 추가';
  if (type === 'quantize') return '양자화 작업 추가';
  if (type === 'llmdeploy') return 'LLM 배포 작업 추가';
  return '배포 작업 추가';
};

export default function EmptyContent({ data }) {
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const { params } = match;
  const { id: workspaceId, tid: pipelineId } = params;

  const { x, type, handleResetData, dataset_info, pipelineType, isStopBtn } =
    data;
  const btnLabel = calBtnLabel(type);

  return (
    <div className={cx('content-cont')}>
      {/* 실행 중(isStopBtn=true)·히스토리('history') 읽기전용에서는 추가 버튼 숨김 (LineContent 동형) */}
      {!isStopBtn && (
        <div className={cx('btn-cont')}>
          <ButtonV2
            type='outline'
            label={
              <div className={cx('btn-label-cont')}>
                <span className={cx('plus-txt')}>+</span>
                <span className={cx('label-txt')}>{btnLabel}</span>
              </div>
            }
            onClick={() => {
              if (!dataset_info?.id) {
                toast.error('학습 데이터셋을 선택해 주세요.');
                return;
              }
              handleAddData(
                dispatch,
                workspaceId,
                pipelineId,
                x,
                0,
                type,
                handleResetData,
                false,
                dataset_info,
              );
            }}
            disabled={pipelineType === 'built-in'}
          />
        </div>
      )}
      {!isStopBtn && <div className={cx('dot-line')} />}
    </div>
  );
}
