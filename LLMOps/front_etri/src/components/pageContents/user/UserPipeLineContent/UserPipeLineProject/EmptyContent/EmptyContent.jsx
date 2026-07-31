import React from 'react';
import { useDispatch } from 'react-redux';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@tango/ui-react';

import { handleAddData } from '../ReactFlowComponent/util';

// CSS Module
import classNames from 'classnames/bind';
import style from './EmptyContent.module.scss';

const cx = classNames.bind(style);

const calBtnLabel = (type) => {
  if (type === 'pre') return '데이터 전처리 작업 추가';
  if (type === 'train') return '학습 작업 추가';
  return '배포 작업 추가';
};

export default function EmptyContent({ data }) {
  const dispatch = useDispatch();
  const match = useRouteMatch();
  const { params } = match;
  const { id: workspaceId, tid: pipelineId } = params;

  const { x, type, handleResetData, dataset_info, pipelineType } = data;
  const btnLabel = calBtnLabel(type);

  return (
    <div className={cx('content-cont')}>
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
            if (!dataset_info.id) {
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
      <div className={cx('dot-line')} />
    </div>
  );
}
