import { getPromptItemInfo } from '@src/apis/llm/prompt';
import BackIcon from '@src/static/images/icon/00-ic-basic-arrow-02-left.svg';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import PromptCommitListDetail from '@src/components/pageContents/llm/PromptContent/PromptContent/PromptCommitListDetail';
import { handleBackGo } from '@src/components/pageContents/llm/PromptContent/PromptHeader/PromptHeader';

import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptCommitPage.module.scss';

const cx = classNames.bind(style);

const initial = {
  system_message: '-',
  user_message: '-',
  name: '-',
  description: '-',
  create_datetime: '0000-00-00 00:00:00',
  update_datetime: '0000-00-00 00:00:00',
  owner: '-',
};

const getPromptList = async (promptId, commitId, setData) => {
  const { status, message, result } = await getPromptItemInfo(
    promptId,
    commitId,
  );
  if (status === STATUS_SUCCESS) {
    setData(result);
  } else {
    toast.error(message);
  }
};

export default function PromptCommitPage() {
  const { t } = useTranslation();
  const history = useHistory();
  const match = useRouteMatch();
  const { did: promptId, tid } = match.params;

  const tidSplit = tid.split('-');
  const commitId = tidSplit[0];
  const commitMessage = tidSplit[1];

  const [data, setData] = useState(initial);
  const { system_message, user_message, name, update_datetime, owner } = data;

  const nameSplit = name.split(': ');
  const commitName = nameSplit[1] ?? '-';
  const projectName = nameSplit[0];

  // ! [사이드 이펙트] 데이터 렌더
  useEffect(() => {
    getPromptList(promptId, commitId, setData);
  }, [commitId, promptId]);

  return (
    <div className={cx('wrapper')}>
      <div className={cx('back-btn')} onClick={() => handleBackGo(history)}>
        <img src={BackIcon} alt='back-icon' />
        <span>{t('commitList.label')}</span>
      </div>
      <div className={cx('header-content-cont')}>
        <div className={cx('title-cont')}>
          <h2 className={cx('commit-title')}>{commitName}</h2>
          <span className={cx('project-txt')}>
            {projectName !== '-' && projectName}
          </span>
        </div>
      </div>
      <PromptCommitListDetail
        commitName={commitName}
        commitMessage={commitMessage}
        update_datetime={update_datetime}
        owner={owner}
        system_message={system_message}
        user_message={user_message}
      />
    </div>
  );
}
