import { InputText, Textarea } from '@tango/ui-react';

import { getPromptItemInfo, postPromptCommit } from '@src/apis/llm/prompt';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { handleSetPromptState } from '@src/store/modules/llmprompt';
import { closeModal } from '@src/store/modules/modal';

import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptCommitModal.module.scss';

const cx = classNames.bind(style);

const initial = {
  commitName: '',
  commitMessage: '',
};

const calFooterMessage = (promptValue, t) => {
  const { commitName, commitMessage } = promptValue;
  if (!commitName) return t('commitName.message');
  if (!commitMessage) return t('commitMessage.placeholder');
  return '';
};

const handleInput = (e, type, setPromptValue) => {
  setPromptValue((prev) => ({
    ...prev,
    [type]: e.target.value,
  }));
};

export default function PromptCommitModal({ data, type }) {
  const dispatch = useDispatch();
  const { t } = useTranslation();
  const title = t('commit.label');

  const { prompt } = data;
  const { prompt_id, prompt_name, prompt_system_message, prompt_user_message } =
    prompt;

  const [promptValue, setPromptValue] = useState(initial);
  const footerMessage = calFooterMessage(promptValue, t);
  const validate = !footerMessage;

  const cancel = useMemo(() => {
    return {
      text: t('cancel.label'),
      func: () => {
        dispatch(closeModal(type));
      },
    };
  }, [dispatch, t, type]);

  const submit = {
    text: t('commit.label'),
    func: async () => {
      const { commitName, commitMessage } = promptValue;
      const { status, message } = await postPromptCommit({
        prompt_id,
        commit_name: commitName,
        commit_message: commitMessage,
        system_message: prompt_system_message,
        user_message: prompt_user_message,
      });
      if (status === STATUS_SUCCESS) {
        if (type === 'PROMPT_PROMPT_COMMIT') {
          const { result, message, status } = await getPromptItemInfo(
            prompt_id,
          );
          if (status === STATUS_SUCCESS) {
            dispatch(
              handleSetPromptState({
                type: 'all',
                info: {
                  ...result,
                  system_message: result.system_message ?? '',
                  user_message: result.user_message ?? '',
                },
                originInfo: {
                  ...result,
                  system_message: result.system_message ?? '',
                  user_message: result.user_message ?? '',
                },
              }),
            );
          } else {
            toast.error(message);
          }
        }
        dispatch(closeModal(type));
      } else {
        toast.error(message);
      }
    },
  };

  return (
    <NewStyleModalFrame
      title={title}
      type={type}
      cancel={cancel}
      submit={submit}
      validate={validate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('flex-32')}>
        {prompt_name && (
          <InputBoxWithLabel
            labelText={t('commit.prompt.label')}
            labelSize='large'
            disableErrorMsg
          >
            <InputText
              size='medium'
              value={prompt_name}
              isReadOnly={true}
              name='projectName'
            />
          </InputBoxWithLabel>
        )}
        <InputBoxWithLabel
          labelText={t('commitName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='commitName'
            placeholder={t('commitName.message')}
            value={promptValue.commitName}
            onChange={(e) => handleInput(e, 'commitName', setPromptValue)}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('commitMessage.label')}
          labelSize='large'
          disableErrorMsg
        >
          <Textarea
            size='medium'
            name='commitMessage'
            placeholder={t('commitMessage.placeholder')}
            value={promptValue.commitMessage}
            onChange={(e) => handleInput(e, 'commitMessage', setPromptValue)}
            customStyle={{ fontSize: '14px', height: '160px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
}
