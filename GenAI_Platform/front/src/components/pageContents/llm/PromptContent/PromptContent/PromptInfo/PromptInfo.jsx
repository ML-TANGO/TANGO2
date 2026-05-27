import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { Prompt, useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2, Textarea } from '@jonathan/ui-react';

import { putPromptsDescription } from '@src/apis/llm/prompt';
import { handleSetPromptState } from '@src/store/modules/llmprompt';
import { handleOpenPopup } from '@src/store/modules/popupState';

import PlaygroundFrame from '../../../PlaygroundContent/PlaygroundFrame';

import classNames from 'classnames/bind';
import style from './PromptInfo.module.scss';

import EditIcon from '@src/static/images/icon/00-ic-basic-pen.svg';

const cx = classNames.bind(style);

// ** [계산] 프로젝트 템플릿에 변경 사항 체크하는 함수 **
export const calDiffProjectTemplate = (
  system_message,
  user_message,
  server_system_message,
  server_user_message,
) => {
  if (
    server_system_message !== system_message ||
    server_user_message !== user_message
  )
    return true;

  return false;
};

// ** [액션] 수정 버튼 핸들러 **
const handleModifyDesc = async (promptId, description, setIsDescription) => {
  await putPromptsDescription(promptId, description);
  setIsDescription(false);
};

// ** [액션] 설명 INPUT 핸들러 **
const handleDesc = (e, dispatch, info) => {
  dispatch(
    handleSetPromptState({
      type: 'info',
      info: {
        ...info,
        description: e.target.value,
      },
    }),
  );
};

// ** [액션] 프로젝트 템플릿 핸들러 **
const handleProjectTemplate = (e, dispatch, info, type) => {
  dispatch(
    handleSetPromptState({
      type: 'info',
      info: {
        ...info,
        [type]: e.target.value,
      },
    }),
  );
};

export default function PromptInfo({ selectedTab }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();

  const match = useRouteMatch();
  const { id: workspaceId, did: promptId } = match.params;
  const { info } = useSelector((state) => state.llmprompt, shallowEqual);
  const {
    system_message: server_system_message,
    user_message: server_user_message,
  } = useSelector((state) => state.llmprompt.originInfo, shallowEqual);

  const {
    description,
    create_datetime,
    update_datetime,
    owner,
    system_message,
    user_message,
  } = info;

  const [isDescription, setIsDescription] = useState(false);

  // ** [데이터] 프로젝트 템플릿 변경 사항 **
  const isDiff = calDiffProjectTemplate(
    system_message,
    user_message,
    server_system_message,
    server_user_message,
  );

  // ** [데이터] 이동 허락 **
  const [isHistoryAllow, setIsHistoryAllow] = useState(false);

  // ** [액션] 페이지 나갈 때 핸들러 **
  let historyGo;
  const handleLeavePopup = (location) => {
    dispatch(
      handleOpenPopup({
        type: 'delete',
        popupTitle: '프롬프트 입력 종료',
        popupContents:
          '프롬프트 입력을 종료하시겠습니까?\n커밋하지 않은 내용은 복구할 수 없습니다.',
        cancelBtnLabel: t('cancel.label'),
        submitBtnLabel: t('end.label'),
        handleCancel: () => {
          setIsHistoryAllow(false);
        },
        handleSubmit: () => {
          setIsHistoryAllow(true);
          historyGo = setTimeout(() => {
            history.push(location.pathname);
          }, 0);
        },
      }),
    );
  };

  // ** [액션] Prompt when 조건일 때 history 방지 **
  const handlePromptMessage = (location, handleLeavePopup) => {
    handleLeavePopup(location);
    return false; // 이동 차단
  };

  useEffect(() => {
    return () => {
      if (historyGo) {
        clearTimeout(historyGo);
      }
    };
  }, [historyGo]);

  return (
    <div className={cx('prompt-info-cont')}>
      <Prompt
        when={isDiff && !selectedTab && !isHistoryAllow} // isDiff가 true일 때만 동작
        message={(location) => handlePromptMessage(location, handleLeavePopup)}
      />
      <PlaygroundFrame style={{ height: '100%' }}>
        <div className={cx('flex-32')}>
          <h3 className={cx('title')}>{t('information.label')}</h3>
          <div className={cx('edit-cont')}>
            <div className={cx('explain-cont')}>
              <div className={cx('label-cont')}>
                <span className={cx('label')}>
                  {t('template.searchPlaceholderDescription.label')}
                </span>
                {!isDescription && (
                  <img
                    src={EditIcon}
                    alt='edit-icon'
                    onClick={() => setIsDescription(true)}
                  />
                )}
              </div>
              {isDescription && (
                <ButtonV2
                  label={t('update.label')}
                  colorType='skyblue'
                  onClick={() =>
                    handleModifyDesc(promptId, description, setIsDescription)
                  }
                />
              )}
            </div>
            <Textarea
              size='large'
              placeholder={t('playground.add.desc.placeholder')}
              value={description}
              name='description'
              onChange={(e) => handleDesc(e, dispatch, info)}
              customStyle={{
                fontSize: '14px',
                display: !isDescription && 'none',
              }}
            />
            {!isDescription && (
              <p className={cx('desc-cont')}>
                {description.length ? description : '-'}
              </p>
            )}
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>{t('accessType.label')}</span>
            <div className={cx('flex-row-16')}>
              <span className={cx('label')}>Private</span>
              <p className={cx('value')}>
                user1, user2, user1, user2, aaron123123, user2, user1, user2
              </p>
            </div>
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>{t('owner.label')}</span>
            <span className={cx('value')}>{owner}</span>
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}> {t('createdAt.label')}</span>
            <span className={cx('value')}>{create_datetime}</span>
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>{t('recent.updateAt.label')}</span>
            <span className={cx('value')}>{update_datetime}</span>
          </div>
        </div>
      </PlaygroundFrame>
      <PlaygroundFrame>
        <div className={cx('flex-32')}>
          <h3 className={cx('title')}>{t('project.template.label')}</h3>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>System</span>
            <Textarea
              customStyle={{ height: '312px' }}
              placeholder={t('prompt.placeholder.label')}
              value={system_message}
              onChange={(e) =>
                handleProjectTemplate(e, dispatch, info, 'system_message')
              }
            />
          </div>
          <div className={cx('flex-16')}>
            <span className={cx('label')}>User</span>
            <Textarea
              value={user_message}
              onChange={(e) =>
                handleProjectTemplate(e, dispatch, info, 'user_message')
              }
              customStyle={{ height: '312px' }}
              placeholder={t('prompt.placeholder.label')}
            />
          </div>
        </div>
      </PlaygroundFrame>
    </div>
  );
}
