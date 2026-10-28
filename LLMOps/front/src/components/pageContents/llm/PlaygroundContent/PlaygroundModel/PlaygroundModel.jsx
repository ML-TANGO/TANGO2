import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@jonathan/ui-react';

import {
  handleSetModelValue,
  handleSetPlaygroundState,
  initialLLMPlaygroundState,
} from '@src/store/modules/llmPlayground';
//
import { openModal } from '@src/store/modules/modal';

import PlaygroundFrame from '../PlaygroundFrame';
import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';

import { calPlusNineHours } from '@src/utils';

import classNames from 'classnames/bind';
import style from './PlaygroundModel.module.scss';

import CloseIcon from '@src/static/images/icon/00-ic-black-close.svg';
import DisabledCloseIcon from '@src/static/images/icon/delete-x-gray.svg';
import IconAllmModel from '@src/static/images/icon/ic-allm-model.svg';
import IconSmile from '@src/static/images/icon/ic-smile.png';

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

// 서빙 엔진 옵션(멀티엔진 로드맵). vLLM + llama.cpp(GGUF 직접/HF 온더플라이 변환)
//   + Phase 3 Tier B(외부 HTTP 서버 어댑터 serving_adapter): TGI/Ollama/Triton/TensorRT 활성.
const ENGINES = [
  { id: 'vllm', label: 'vLLM', disabled: false },
  { id: 'llama_cpp', label: 'llama.cpp', disabled: false },
  { id: 'tgi', label: 'TGI', disabled: false },
  { id: 'ollama', label: 'Ollama', disabled: false },
  { id: 'triton', label: 'Triton', disabled: false },
  // TensorRT: Phase 3 Tier B, trtllm-serve(OpenAI 호환, PyTorch 백엔드로 HF 직접) 어댑터로 배선.
  { id: 'tensorrt', label: 'TensorRT', disabled: false },
];

const PlaygroundModel = React.memo(function PlaygroundModel({
  workspaceId,
  value,
  onChange,
  disabled,
  title,
  allmOnly = false,
  allowExternal = true,
  // 이중 배포는 vLLM 고정이라 엔진 선택 UI 를 숨긴다(기본 true = 단일 화면 그대로 노출).
  showServingEngine = true,
}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const reduxModel = useSelector(
    (state) => state.llmPlayground.model,
    shallowEqual,
  );
  // value가 있을 때만 역할별 controlled mode를 사용한다.
  // 기존 단일 화면은 value를 넘기지 않으므로 Redux 계약과 렌더링이 그대로 유지된다.
  const isControlled = value !== undefined;
  const currentModel = isControlled
    ? value || initialLLMPlaygroundState.model
    : reduxModel;

  const {
    model_type,
    serving_system,
    model_huggingface_id,
    model_allm_name,
    model_allm_commit_name,
    model_temperature,
    model_top_p,
    model_top_k,
    model_repetition_penalty,
    model_max_new_tokens,
    description,
    commit,
    access,
    create_datetime,
    update_datetime,
  } = currentModel;

  const { id } = useSelector((state) => state.llmPlayground.info, shallowEqual);

  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  const isDisabled = disabled ?? calIsDeployLoading(statusType);

  const handleRangeBar = useCallback(
    (e, label) => {
      const changeType = Tlabel[label];
      const modelValue = +e.target.value;

      if (isControlled) {
        onChange?.({ ...currentModel, [changeType]: modelValue });
        return;
      }

      dispatch(
        handleSetModelValue({
          type: changeType,
          modelValue,
        }),
      );
    },
    [currentModel, dispatch, isControlled, onChange],
  );

  const handleSelectEngine = useCallback(
    (engineId) => {
      // 활성(비-disabled) 엔진만 반영. disabled 는 버튼단에서도 막지만 방어.
      const eng = ENGINES.find((e) => e.id === engineId);
      if (!eng || eng.disabled) return;
      if (isControlled) {
        onChange?.({ ...currentModel, serving_system: engineId });
        return;
      }
      dispatch(
        handleSetModelValue({ type: 'serving_system', modelValue: engineId }),
      );
    },
    [currentModel, dispatch, isControlled, onChange],
  );

  const handleOpenModelImport = useCallback(() => {
    if (isDisabled) return;
    if (!isControlled && !id)
      return toast.error(t('playground.header.connecting.message'));
    dispatch(
      openModal({
        modalType: 'IMPORT_MODEL_PLAYGROUND',
        modalData: {
          workspaceId,
          submit: {
            text: 'select.label',
          },
          cancel: {
            text: 'cancel.label',
          },
          // controlled mode에서는 import modal이 Redux를 갱신하지 않고 역할 소유자에게만 결과를 돌려준다.
          ...(isControlled && {
            onSelect: (selectedModel) => {
              if (
                !allowExternal &&
                selectedModel.training_type === 'external'
              ) {
                toast.error('LLM1은 내부 텍스트 모델만 선택할 수 있습니다.');
                return false;
              }
              onChange?.({ ...currentModel, ...selectedModel });
              return true;
            },
            allmOnly,
            allowExternal,
          }),
        },
      }),
    );
  }, [
    allmOnly,
    allowExternal,
    currentModel,
    dispatch,
    id,
    isControlled,
    isDisabled,
    onChange,
    t,
    workspaceId,
  ]);

  const handleRefreshRangeBar = useCallback(
    (label) => {
      const changeType = Tlabel[label];
      const refreshValue = TValue[changeType];

      if (isControlled) {
        onChange?.({ ...currentModel, [changeType]: refreshValue });
        return;
      }
      dispatch(
        handleSetModelValue({
          type: changeType,
          modelValue: refreshValue,
        }),
      );
    },
    [currentModel, dispatch, isControlled, onChange],
  );

  const handleDeleteModel = useCallback(() => {
    if (isControlled) {
      onChange?.({ ...initialLLMPlaygroundState.model });
      return;
    }
    dispatch(
      handleSetPlaygroundState({
        type: 'model',
        model: {
          ...initialLLMPlaygroundState.model,
        },
      }),
    );
  }, [dispatch, isControlled, onChange]);
  const engineLabelId = isControlled
    ? `serving-engine-label-${String(title || 'controlled').replace(
        /\s+/g,
        '-',
      )}`
    : 'serving-engine-label';

  return (
    <PlaygroundFrame disabled={isDisabled}>
      <div className={cx('header')}>
        <h3 className={cx('title')}>{title ?? t('Model')}</h3>
      </div>
      {showServingEngine && (
        <div className={cx('engine-select')}>
          <span className={cx('engine-label')} id={engineLabelId}>
            서빙 엔진
          </span>
          <div
            className={cx('engine-options')}
            role='radiogroup'
            aria-labelledby={engineLabelId}
          >
            {ENGINES.map((eng) => {
              const selected = (serving_system || 'vllm') === eng.id;
              return (
                <button
                  key={eng.id}
                  type='button'
                  role='radio'
                  aria-checked={selected}
                  className={cx(
                    'engine-opt',
                    selected && 'selected',
                    eng.disabled && 'disabled',
                  )}
                  disabled={eng.disabled || isDisabled}
                  onClick={() => handleSelectEngine(eng.id)}
                >
                  {eng.label}
                  {eng.disabled && <span className={cx('badge')}>준비중</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
      {!model_type && (
        <ButtonV2
          label={t('model.import.label')}
          type='outline'
          size='m'
          style={{ width: '100%', marginBottom: '32px' }}
          disabled={isDisabled}
          onClick={handleOpenModelImport}
        />
      )}
      {model_type && (
        <>
          <div className={cx('seleced-model-cont', isDisabled && 'disabled')}>
            <div className={cx('left')}>
              <div className={cx('model', isDisabled && 'disabled')}>
                <img
                  className={cx('icon')}
                  src={!model_type ? IconSmile : IconAllmModel}
                  alt='smile-icon'
                />
                {model_type === 'huggingface'
                  ? model_huggingface_id
                  : model_allm_name}
              </div>
              {model_type === 'commit' && (
                <div className={cx('version', isDisabled && 'disabled')}>
                  {model_allm_commit_name}
                </div>
              )}
            </div>
            <button
              onClick={handleDeleteModel}
              alt='모델 삭제 버튼'
              disabled={isDisabled}
              className={cx('button')}
            >
              <img
                className={cx('close')}
                src={isDisabled ? DisabledCloseIcon : CloseIcon}
                alt=''
              />
            </button>
          </div>
          <div className={cx('border')}></div>
          <div className={cx('flex-32')}>
            <div className={cx('row')}>
              <span className={cx('label')}>{t('description.label')}</span>
              <p className={cx('value')}>{description ?? '-'}</p>
            </div>
            <div className={cx('row')}>
              <span className={cx('label')}>커밋 버전</span>
              <p className={cx('value')}>{commit ?? '-'}</p>
            </div>
            <div className={cx('row')}>
              <span className={cx('label')}>접근 권한</span>
              <p className={cx('value')}>{access ? 'Public' : 'Private'}</p>
            </div>
            <div className={cx('row')}>
              <span className={cx('label')}>생성 일시</span>
              <p className={cx('value')}>
                {calPlusNineHours(create_datetime) ?? '0000-00-00 00:00:00'}
              </p>
            </div>
            <div className={cx('row')}>
              <span className={cx('label')}>최근 업데이트 일시</span>
              <p className={cx('value')}>
                {update_datetime ? calPlusNineHours(update_datetime) : '-'}
              </p>
            </div>
          </div>
        </>
      )}
    </PlaygroundFrame>
  );
});

export default PlaygroundModel;
