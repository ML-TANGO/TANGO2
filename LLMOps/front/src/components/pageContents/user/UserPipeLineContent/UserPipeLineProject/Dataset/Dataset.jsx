import React from 'react';
import { useRouteMatch } from 'react-router-dom';

import SelectBox from '@src/components/atoms/SelectBox';

import classNames from 'classnames/bind';
import style from './Dataset.module.scss';

const cx = classNames.bind(style);

export default function Dataset({
  datasetOptions,
  dataset_info,
  isStopBtn,
  handleDataset,
  pipelineType,
}) {
  const match = useRouteMatch();
  const { params } = match;
  const { tid: pipelineId } = params;

  const { id } = dataset_info;

  return (
    <div className={cx('dataset-cont')}>
      <div className={cx('accordion-cont')}>
        <h3 className={cx('dataset-title')}>학습 데이터셋</h3>
        <div className={cx('dropdown-cont')}>
          <SelectBox
            value={id}
            list={datasetOptions}
            handleOptionClick={(value) => {
              handleDataset(value, pipelineId);
            }}
            placeholder={'데이터셋을 선택하세요.'}
            style={{ height: '36px', padding: '16px', backgroundColor: '#fff' }}
            disabled={isStopBtn}
          />
        </div>
      </div>
    </div>
  );
}
