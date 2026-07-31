import React from 'react';

import PlaygroundFrame from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from '../../UserPipeLineInfo.module.scss';

const cx = classNames.bind(style);

export default function TrainDataset({ ...datasetInfo }) {
  const { name, description, create_datetime, create_user_name } = datasetInfo;

  return (
    <PlaygroundFrame>
      <div className={cx('row')}>
        <h2>학습 데이터셋</h2>
        <span className={cx('training-dataset-txt')}>{name ?? '-'}</span>
        <div className={cx('label-cont')}>
          <span className={cx('label')}>설명</span>
          <p className={cx('value')}>{description ?? '-'}</p>
        </div>
        <div className={cx('label-cont')}>
          <span className={cx('label')}>소유자</span>
          <span className={cx('value')}>{create_user_name ?? '-'}</span>
        </div>
        <div className={cx('label-cont')}>
          <span className={cx('label')}>생성 일시</span>
          <span className={cx('value')}>
            {create_datetime ?? '0000-00-00 00:00:00'}
          </span>
        </div>
      </div>
    </PlaygroundFrame>
  );
}
