import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import CardTemplate from '@src/components/molecules/CardTemplate/CardTemplate';
import { breadCrumbHandler } from '@src/components/pageContents/user/UserPipeLineContent/UserPipeLineMenu/util';

import {
  deletePromptBookMark,
  deletePrompts,
  getPrompts,
  postPromptBookMark,
} from '@src/apis/llm/prompt';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

// CSS Module
import classNames from 'classnames/bind';
import style from './PromptMenuPage.module.scss';

const cx = classNames.bind(style);

const getPromptList = async (workspaceId, setPromptMenuList) => {
  const { status, message, result } = await getPrompts(workspaceId);
  if (status === STATUS_SUCCESS) {
    const transformList = result.map((el) => {
      return {
        ...el,
        title: el.name,
        subTitle: el.description,
        constructor: el.owner,
        updateTime: el.update_datetime,
        createTime: el.create_datetime,
        isBookMark: el.bookmark,
        isAccess: el.access,
      };
    });
    const sortArr = transformList.sort((a, b) => b.isBookMark - a.isBookMark);
    setPromptMenuList(sortArr);
  } else {
    toast.error(message);
  }
};

export default function PromptMenuPage() {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const dispatch = useDispatch();
  const history = useHistory();
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const { id: workspace_id } = match.params;
  const [promptMenuList, setPromptMenuList] = useState([]);

  const handleCreateCard = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'ADD_PROMPT_MODAL',
        modalData: {
          workspace_id,
          handleRefresh: async () =>
            await getPromptList(workspace_id, setPromptMenuList),
        },
      }),
    );
  }, [dispatch, workspace_id]);

  const handleOnClickCard = useCallback(
    (e, id, constructor, isAccess) => {
      e.stopPropagation();
      if (!isAccess && userName !== constructor) return;

      history.push(`/user/workspace/${workspace_id}/prompt/${id}/promptinfo`);
    },
    [userName, history, workspace_id],
  );

  const handleDelete = useCallback(
    async (e, id, title) => {
      e.stopPropagation();

      dispatch(
        openConfirm({
          title: 'deleteTrainingPopup.title.label',
          content: `프롬프트를 삭제하시겠습니까?\n삭제된 프롬프트는 복구할 수 없습니다.\n\n\n프롬프트를 삭제하시려면 아래 란에 프롬프트 이름\n${title}을 입력해 주세요.`,
          testid: 'training-delete-modal',
          submit: {
            text: 'delete.label',
            func: async () => {
              const { status, message } = await deletePrompts(id);
              if (status === STATUS_SUCCESS) {
                await getPromptList(workspace_id, setPromptMenuList);
              } else {
                toast.error(message);
              }
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          confirmMessage: title,
        }),
      );
    },
    [dispatch, workspace_id],
  );

  const handleBookMark = useCallback(
    async (e, id, isBookMark) => {
      e.stopPropagation();
      if (!isBookMark) {
        await postPromptBookMark(id);
      } else {
        await deletePromptBookMark(id);
      }
      await getPromptList(workspace_id, setPromptMenuList);
    },
    [workspace_id],
  );

  const handleEdit = useCallback(
    async (e, id) => {
      e.stopPropagation();

      const { result, message, status } = await getPrompts(
        workspace_id,
        setPromptMenuList,
      );

      if (status === STATUS_SUCCESS) {
        const prompt_item = result.find((info) => info.id === id);
        dispatch(
          openModal({
            modalType: 'EDIT_PROMPT_MODAL',
            modalData: {
              workspace_id,
              prompt_item,
              handleRefresh: async () => {
                await getPromptList(workspace_id, setPromptMenuList);
              },
            },
          }),
        );
      } else {
        toast.error(message);
      }
    },
    [dispatch, workspace_id],
  );

  useEffect(() => {
    getPromptList(workspace_id, setPromptMenuList);
  }, [dispatch, workspace_id]);

  return (
    <div className={cx('playground-cont')}>
      <h1 className={cx('title')}>{t('prompt.label')}</h1>
      <CardTemplate
        createLabel={t('prompt.add.label')}
        cardItems={promptMenuList}
        handleCreateCard={handleCreateCard}
        handleOnClickCard={handleOnClickCard}
        handleBookMark={(e, id, isBookMark) =>
          handleBookMark(e, id, isBookMark)
        }
        handleEdit={handleEdit}
        handleDelete={(e, id, title) => handleDelete(e, id, title)}
      />
    </div>
  );
}
