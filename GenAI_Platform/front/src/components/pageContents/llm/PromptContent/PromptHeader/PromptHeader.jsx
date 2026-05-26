import { ButtonV2 } from '@jonathan/ui-react';

import BackIcon from '@src/static/images/icon/00-ic-basic-arrow-02-left.svg';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { openModal } from '@src/store/modules/modal';

import classNames from 'classnames/bind';
import style from './PromptHeader.module.scss';

const cx = classNames.bind(style);

// ** [계산] 헤더 메세지 계산 함수 **
const calHeaderMessage = (projectTemplate, serverProjectTemplate, t) => {
  const { system_message, user_message } = projectTemplate;
  const { server_system_message, server_user_message } = serverProjectTemplate;

  if (
    !server_system_message &&
    !server_user_message &&
    !system_message &&
    !user_message
  )
    return '';

  if (
    server_system_message !== system_message ||
    server_user_message !== user_message
  )
    return t('prompt.header.save.message');
  if (!system_message || !user_message) return t('prompt.header.write.message');
  return '';
};

// ** [액션] 뒤로가기 핸들러 **
export const handleBackGo = (history) => {
  history.go(-1);
};

// ** [액션] 커밋 불러오기 모달 **
const handleImportCommit = (promptId, dispatch) => {
  dispatch(
    openModal({
      modalType: 'IMPORT_COMMIT_MODAL',
      modalData: {
        promptId,
      },
    }),
  );
};

// ** [액션] 커밋 모달 **
const handleCommit = (promptId, projectTemplate, dispatch) => {
  const { system_message, user_message } = projectTemplate;
  dispatch(
    openModal({
      modalType: 'PROMPT_PROMPT_COMMIT',
      modalData: {
        promptId,
        prompt: {
          prompt_id: promptId,
          prompt_system_message: system_message,
          prompt_user_message: user_message,
        },
      },
    }),
  );
};

export default function PromptHeader({ selectedTab }) {
  const history = useHistory();
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const match = useRouteMatch();
  const { did: promptId } = match.params;

  const { info, originInfo } = useSelector(
    (state) => state.llmprompt,
    shallowEqual,
  );
  const { name, system_message, user_message } = info;
  const {
    system_message: server_system_message,
    user_message: server_user_message,
  } = originInfo;

  const headerMessage = calHeaderMessage(
    { system_message, user_message },
    { server_system_message, server_user_message },
    t,
  );

  const splitName = name.split(': ');
  const displayName = splitName[0];
  const commitName = splitName[1];

  return (
    <div className={cx('header-cont')}>
      <div className={cx('back-btn')} onClick={() => handleBackGo(history)}>
        <img src={BackIcon} alt='back-icon' />
        <span>{t('prompt.label')}</span>
      </div>
      <div className={cx('header-content-cont')}>
        <div className={cx('title-cont')}>
          <h2 className={cx('header-title')}>{displayName}</h2>
          <span className={cx('commit-txt')}>{commitName}</span>
        </div>
        {selectedTab === 0 && (
          <div className={cx('header-content-right')}>
            <p className={cx('error-message-paragraph')}>{headerMessage}</p>
            <ButtonV2
              colorType='skyblue'
              label={t('commitLoad.label')}
              onClick={() => handleImportCommit(promptId, dispatch)}
            />
            <ButtonV2
              colorType='skyblue'
              label={t('commit.label')}
              onClick={() =>
                handleCommit(
                  promptId,
                  { system_message, user_message },
                  dispatch,
                )
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
