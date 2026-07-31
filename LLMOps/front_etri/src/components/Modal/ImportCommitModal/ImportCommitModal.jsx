import { getPromptItemInfo, getPromptList } from '@src/apis/llm/prompt';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import Dropdown from '@src/components/atoms/Dropdown';

import { handleSetPromptState } from '@src/store/modules/llmprompt';
import { closeModal } from '@src/store/modules/modal';

import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './ImportCommitModal.module.scss';

const cx = classNames.bind(style);

const calFooterMessage = (selectedCommit, t) => {
  if (!selectedCommit.value) return t('prompt.warning.label2');
  return '';
};

const getPromptDataList = async (promptId, setCommitList) => {
  const { status, message, result } = await getPromptList(promptId);
  if (status === STATUS_SUCCESS) {
    const transfromResult = result.map((el) => {
      return {
        ...el,
        label: el.name,
        value: el.commit_id,
      };
    });
    setCommitList(transfromResult);
  } else {
    toast.error(message);
  }
};

const handleCommit = (value, setSelectedCommit) => {
  setSelectedCommit(value);
};

export default function ImportCommitModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { promptId } = data;

  const title = useMemo(() => {
    return t('commitLoad.label');
  }, [t]);

  const cancel = useMemo(() => {
    return {
      text: t('cancel.label'),
    };
  }, [t]);

  const submit = {
    text: t('getInfo.label'),
    func: async () => {
      const { result, message, status } = await getPromptItemInfo(
        promptId,
        selectedCommit.commit_id,
      );
      if (status === STATUS_SUCCESS) {
        dispatch(
          handleSetPromptState({
            type: 'all',
            info: {
              ...result,
            },
            originInfo: {
              ...result,
            },
          }),
        );
        dispatch(closeModal(type));
      } else {
        toast.error(message);
      }
    },
  };

  const [commitList, setCommitList] = useState([]);
  const [selectedCommit, setSelectedCommit] = useState({ value: null });

  const footerMessage = calFooterMessage(selectedCommit, t);
  const validate = !footerMessage;

  useEffect(() => {
    getPromptDataList(promptId, setCommitList);
  }, [promptId]);

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
      <Dropdown
        list={commitList}
        style={{ height: '38px', padding: '16px' }}
        value={selectedCommit.value}
        handleOptionClick={(value) => handleCommit(value, setSelectedCommit)}
        placeholder={t('prompt.warning.label2')}
      />
    </NewStyleModalFrame>
  );
}
