import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import { ButtonV2, Switch, Textarea } from '@tango/ui-react';

import {
  handleSetPlaygroundState,
  initialLLMPlaygroundState,
} from '@src/store/modules/llmPlayground';
import { openModal } from '@src/store/modules/modal';

import PlaygroundFrame from '../PlaygroundFrame';
import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';

import classNames from 'classnames/bind';
import style from './PlaygroundPrompt.module.scss';

import IconClose from '@src/static/images/icon/00-ic-black-close.svg';
import DisabledCloseIcon from '@src/static/images/icon/delete-x-gray.svg';

const cx = classNames.bind(style);

const calPromptPlaceholderMessage = (is_prompt, prompt_id, t) => {
  if (!is_prompt) return t('playground.prompt.textarea.placeholder1');
  if (!prompt_id) return t('playground.prompt.textarea.placeholder2');
  return '';
};

const handelInputTextArea = (e, type, dispatch) => {
  dispatch(
    handleSetPlaygroundState({
      type: 'prompt',
      prompt: {
        is_prompt: true,
        [type]: e.target.value,
      },
    }),
  );
};

const handleCommit = (workspaceId, prompt, dispatch) => {
  dispatch(
    openModal({
      modalType: 'PLAYGROUND_PROMPT_COMMIT',
      modalData: {
        workspaceId,
        prompt,
      },
    }),
  );
};

const PlaygroundPrompt = React.memo(({ workspaceId }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const {
    is_prompt,
    prompt_id,
    prompt_name,
    prompt_commit_name,
    prompt_system_message,
    prompt_user_message,
  } = useSelector((state) => state.llmPlayground.prompt, shallowEqual);

  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );
  const isDisabled = calIsDeployLoading(statusType);
  const promptMessage = calPromptPlaceholderMessage(is_prompt, prompt_id, t);

  const handleDeleteRag = useCallback(() => {
    dispatch(
      handleSetPlaygroundState({
        type: 'prompt',
        prompt: {
          ...initialLLMPlaygroundState.prompt,
          is_prompt: !is_prompt,
        },
      }),
    );
  }, [dispatch, is_prompt]);

  const handleSwitch = useCallback(() => {
    handleDeleteRag(is_prompt, dispatch);
  }, [dispatch, handleDeleteRag, is_prompt]);

  const handleOpenPromptImport = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'IMPORT_PROMPT',
        modalData: {
          workspaceId,
        },
      }),
    );
  }, [dispatch, workspaceId]);

  return (
    <PlaygroundFrame>
      <div className={cx('prompt-cont')}>
        <div className={cx('header')}>
          <h3 className={cx('title')}>{t('prompt.label')}</h3>
          <Switch
            name='prompt-switch'
            onChange={handleSwitch}
            checked={
              is_prompt ||
              prompt_name ||
              prompt_system_message ||
              prompt_user_message
            }
            disabled={!!prompt_id}
          />
        </div>
        {!prompt_id && (
          <ButtonV2
            label={`${t('prompt.label')} ${t('getInfo.label')}`}
            type='outline'
            size='m'
            style={{
              width: '100%',
            }}
            disabled={!is_prompt}
            onClick={handleOpenPromptImport}
          />
        )}
        {prompt_id && (
          <div className={cx('selected-prompt-cont', isDisabled && 'disabled')}>
            <div className={cx('prompt-txt-cont')}>
              <span className={cx('name-txt', isDisabled && 'disabled')}>
                {prompt_name}
              </span>
              <span
                className={cx('commit-version-txt', isDisabled && 'disabled')}
              >
                {prompt_commit_name}
              </span>
            </div>
            <button className={cx('rag-delete-btn')} onClick={handleDeleteRag}>
              <img
                src={isDisabled ? DisabledCloseIcon : IconClose}
                alt='close-btn-img'
              />
            </button>
          </div>
        )}
        {prompt_id && <div className={cx('border')} />}
        <div className={cx('textarea-cont')}>
          <div className={cx('system-textarea-cont')}>
            <div className={cx('label-cont')}>
              <span>System</span>
            </div>
            <textarea
              name='user-message'
              placeholder={promptMessage}
              value={prompt_system_message}
              onChange={(e) =>
                handelInputTextArea(e, 'prompt_system_message', dispatch)
              }
              readOnly={!prompt_id || isDisabled}
            />
          </div>
          <div className={cx('system-textarea-cont')}>
            <div className={cx('label-cont')}>
              <span>User</span>
            </div>
            <textarea
              name='user-message'
              placeholder={promptMessage}
              value={prompt_user_message}
              onChange={(e) =>
                handelInputTextArea(e, 'prompt_user_message', dispatch)
              }
              readOnly={!prompt_id || isDisabled}
            />
          </div>
        </div>
        {prompt_id && (
          <ButtonV2
            label={t('commit.label')}
            type='outline'
            style={{ width: '100%' }}
            onClick={() =>
              handleCommit(
                workspaceId,
                {
                  is_prompt,
                  prompt_id,
                  prompt_name,
                  prompt_commit_name,
                  prompt_system_message,
                  prompt_user_message,
                },
                dispatch,
              )
            }
            disabled={isDisabled}
          />
        )}
      </div>
    </PlaygroundFrame>
  );
});

export default PlaygroundPrompt;
