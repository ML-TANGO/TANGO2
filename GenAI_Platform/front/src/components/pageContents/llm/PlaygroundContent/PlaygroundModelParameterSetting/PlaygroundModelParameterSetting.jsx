import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { handleSetModelValue } from '@src/store/modules/llmPlayground';

import PlaygroundFrame from '../PlaygroundFrame';
import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';
import PlaygroundRangeBar from '../PlaygroundRangeBar';

// CSS Module
import classNames from 'classnames/bind';
import style from './PlaygroundModelParameterSetting.module.scss';

const cx = classNames.bind(style);

const Tlabel = {
  Temperature: 'model_temperature',
  'Top P': 'model_top_p',
  'Top K': 'model_top_k',
  'Repetition Penalty': 'model_repetition_penalty',
  'Max Sequence': 'model_max_new_tokens',
};

const TValue = {
  model_temperature: 1,
  model_top_p: 0.9,
  model_top_k: 50,
  model_repetition_penalty: 1.2,
  model_max_new_tokens: 512,
};

export default function PlaygroundModelParameterSetting() {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const {
    model_type,
    model_huggingface_id,
    model_allm_name,
    model_allm_commit_name,
    model_temperature,
    model_top_p,
    model_top_k,
    model_repetition_penalty,
    model_max_new_tokens,
  } = useSelector((state) => state.llmPlayground.model, shallowEqual);

  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  const isDisabled = calIsDeployLoading(statusType);

  const handleRangeBar = useCallback(
    (e, label) => {
      const changeType = Tlabel[label];

      dispatch(
        handleSetModelValue({
          type: changeType,
          modelValue: +e.target.value,
        }),
      );
    },
    [dispatch],
  );

  const handleRefreshRangeBar = useCallback(
    (label) => {
      const changeType = Tlabel[label];
      const refreshValue = TValue[changeType];

      dispatch(
        handleSetModelValue({
          type: changeType,
          modelValue: refreshValue,
        }),
      );
    },
    [dispatch],
  );

  return (
    <PlaygroundFrame>
      <div className={cx('header')}>
        <h3 className={cx('title')}>모델 파라미터 설정</h3>
      </div>
      {!model_type && (
        <div className={cx('empty-cont')}>
          <p className={cx('txt')}>
            모델을 불러오시면, 파라미터가 활성화됩니다.
          </p>
        </div>
      )}
      {model_type && (
        <div className={cx('flex-32')}>
          <PlaygroundRangeBar
            label='Temperature'
            min={0}
            max={2.0}
            step={0.1}
            disabled={isDisabled}
            value={model_temperature}
            onChange={(e, label) => handleRangeBar(e, label, dispatch)}
            handleRefresh={handleRefreshRangeBar}
          />
          <PlaygroundRangeBar
            label='Top P'
            min={0}
            max={1.0}
            step={0.1}
            disabled={isDisabled}
            value={model_top_p}
            onChange={handleRangeBar}
            handleRefresh={handleRefreshRangeBar}
          />
          <PlaygroundRangeBar
            label='Top K'
            min={0}
            max={100}
            step={1}
            disabled={isDisabled}
            value={model_top_k}
            onChange={handleRangeBar}
            handleRefresh={handleRefreshRangeBar}
          />
          <PlaygroundRangeBar
            label='Repetition Penalty'
            min={0}
            max={2.0}
            step={0.1}
            disabled={isDisabled}
            value={model_repetition_penalty}
            onChange={handleRangeBar}
            handleRefresh={handleRefreshRangeBar}
          />
          <PlaygroundRangeBar
            label='Max Sequence'
            min={0}
            max={2048}
            step={1}
            disabled={isDisabled}
            value={model_max_new_tokens}
            onChange={handleRangeBar}
            handleRefresh={handleRefreshRangeBar}
          />
        </div>
      )}
    </PlaygroundFrame>
  );
}
