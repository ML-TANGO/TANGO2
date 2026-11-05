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

// Redux 키(model_*) → 제어 모드 bare 키. 이중 배포는 역할별(LLM1/LLM2) 값을 호출부가
//   들고 있어야 해서 단일 스코프인 llmPlayground Redux 를 쓸 수 없다.
const TBareKey = {
  model_temperature: 'temperature',
  model_top_p: 'top_p',
  model_top_k: 'top_k',
  model_repetition_penalty: 'repetition_penalty',
  model_max_new_tokens: 'max_new_tokens',
};

/**
 * 모델 파라미터 설정 카드.
 *   - 비제어(기본): 단일 배포 상세 — llmPlayground Redux 를 읽고/쓴다(종전 동작 그대로).
 *   - 제어(value 전달): 이중 배포 상세 — 역할별 값을 프롭으로 받고 onChange 로 올려보낸다.
 * 파라미터는 배포 시점에 서빙 컨테이너로 주입되므로 편집 가능 여부는 호출부가 disabled 로 정한다.
 */
export default function PlaygroundModelParameterSetting({
  title = '모델 파라미터 설정',
  value = null,
  onChange = null,
  disabled: disabledProp = undefined,
  isReady = undefined,
  emptyText = '모델을 불러오시면, 파라미터가 활성화됩니다.',
  defaults = null,
} = {}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const isControlled = value != null;

  const {
    model_type,
    model_huggingface_id,
    model_allm_name,
    model_allm_commit_name,
    model_temperature: rdxTemperature,
    model_top_p: rdxTopP,
    model_top_k: rdxTopK,
    model_repetition_penalty: rdxRepetitionPenalty,
    model_max_new_tokens: rdxMaxNewTokens,
  } = useSelector((state) => state.llmPlayground.model, shallowEqual);

  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );

  // 제어 모드에서는 단일 스코프 Redux 의 model_type/status 를 신뢰하지 않는다.
  const isDisabled = isControlled
    ? !!disabledProp
    : (disabledProp ?? calIsDeployLoading(statusType));
  const hasModel = isControlled ? !!isReady : !!model_type;

  const model_temperature = isControlled ? value.temperature : rdxTemperature;
  const model_top_p = isControlled ? value.top_p : rdxTopP;
  const model_top_k = isControlled ? value.top_k : rdxTopK;
  const model_repetition_penalty = isControlled
    ? value.repetition_penalty
    : rdxRepetitionPenalty;
  const model_max_new_tokens = isControlled
    ? value.max_new_tokens
    : rdxMaxNewTokens;

  const applyValue = useCallback(
    (changeType, modelValue) => {
      if (isControlled) {
        onChange?.(TBareKey[changeType], modelValue);
        return;
      }
      dispatch(handleSetModelValue({ type: changeType, modelValue }));
    },
    [isControlled, onChange, dispatch],
  );

  const handleRangeBar = useCallback(
    (e, label) => {
      applyValue(Tlabel[label], +e.target.value);
    },
    [applyValue],
  );

  const handleRefreshRangeBar = useCallback(
    (label) => {
      const changeType = Tlabel[label];
      // 이중 배포는 역할별 기본값(top_k=-1)을 쓰므로 호출부 기본값을 우선하고,
      // 프롭이 없는 단일 화면은 기존 TValue 초기화 동작을 그대로 유지한다.
      const resetValue =
        defaults?.[TBareKey[changeType]] ?? TValue[changeType];
      applyValue(changeType, resetValue);
    },
    [applyValue, defaults],
  );

  return (
    <PlaygroundFrame>
      <div className={cx('header')}>
        <h3 className={cx('title')}>{title}</h3>
      </div>
      {!hasModel && (
        <div className={cx('empty-cont')}>
          <p className={cx('txt')}>{emptyText}</p>
        </div>
      )}
      {hasModel && (
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
            min={-1}
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
            min={1}
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
