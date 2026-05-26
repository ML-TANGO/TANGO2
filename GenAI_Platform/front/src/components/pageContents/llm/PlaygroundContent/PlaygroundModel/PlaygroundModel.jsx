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

const PlaygroundModel = React.memo(({ workspaceId }) => {
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
    description,
    commit,
    access,
    create_datetime,
    update_datetime,
  } = useSelector((state) => state.llmPlayground.model, shallowEqual);

  const { id } = useSelector((state) => state.llmPlayground.info, shallowEqual);

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

  const handleOpenModelImport = useCallback(() => {
    if (!id) return toast.error(t('playground.header.connecting.message'));
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
        },
      }),
    );
  }, [dispatch, id, t, workspaceId]);

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

  const handleDeleteModel = useCallback(() => {
    dispatch(
      handleSetPlaygroundState({
        type: 'model',
        model: {
          ...initialLLMPlaygroundState.model,
        },
      }),
    );
  }, [dispatch]);

  return (
    <PlaygroundFrame>
      <div className={cx('header')}>
        <h3 className={cx('title')}>{t('Model')}</h3>
      </div>
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
