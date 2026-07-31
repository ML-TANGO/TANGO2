import React, { useCallback, useEffect, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import CardList from '@src/components/molecules/CardTemplate/CardList';
import CreateCard from '@src/components/molecules/CardTemplate/CreateCard';

import {
  deletePipeLines,
  putPipelineBookmark,
} from '@src/apis/flightbase/pipeline';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import CardItem from './CardItem';

import { breadCrumbHandler, getPipelineMenu } from './util';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserPipeLineMenu.module.scss';

const cx = classNames.bind(style);

export default function UserPipeLineMenu() {
  const history = useHistory();
  const dispatch = useDispatch();

  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [cardData, setCardData] = useState([]);

  const handelRefresh = useCallback(async () => {
    await getPipelineMenu(workspaceId, setCardData);
  }, [workspaceId]);

  const handleCreateCard = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'AI_PIPELINE_ADD',
        modalData: {
          workspaceId,
          handleRefresh: handelRefresh,
        },
      }),
    );
  }, [dispatch, handelRefresh, workspaceId]);

  const handleOnClickCard = useCallback(
    (e, id, constructor) => {
      e.stopPropagation();
      const findCardItem = cardData.find((el) => el.id === id);
      const { isAccess, private_user_list } = findCardItem;

      if (isAccess === 0) {
        if (userName !== constructor) {
          const isEditAccess = private_user_list.find(
            ({ user_name }) => user_name === userName,
          );
          if (!isEditAccess) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }
      history.push(`/user/workspace/${workspaceId}/pipeline/${id}`);
    },
    [cardData, history, userName, workspaceId],
  );

  const handleEdit = useCallback(
    (e, title, id, subTitle, constructor, isAccess, private_user_list) => {
      e.stopPropagation();

      if (isAccess === 0) {
        if (userName !== constructor) {
          const isEditAccess = private_user_list.find(
            ({ user_name }) => user_name === userName,
          );
          if (!isEditAccess) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }

      const transfromUserList = private_user_list.map((info) => ({
        label: info.user_name,
        value: info.user_id,
      }));

      dispatch(
        openModal({
          modalType: 'EDIT_PIPELINE_MODAL',
          modalData: {
            workspaceId,
            handleRefresh: handelRefresh,
            title,
            id,
            subTitle,
            constructor,
            isAccess,
            private_user_list: transfromUserList,
          },
        }),
      );
    },
    [dispatch, handelRefresh, userName, workspaceId],
  );

  const handleBookMark = useCallback(
    async (e, id) => {
      e.stopPropagation();
      const { status, message } = await putPipelineBookmark(id);
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      } else {
        await handelRefresh();
      }
    },
    [handelRefresh],
  );

  const handleDelete = useCallback(
    async (e, id, title, isAccess, constructor, private_user_list) => {
      e.stopPropagation();

      if (isAccess === 0) {
        if (userName !== constructor) {
          const isEditAccess = private_user_list.find(
            ({ user_name }) => user_name === userName,
          );
          if (!isEditAccess) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }

      dispatch(
        openConfirm({
          title: 'pipeline.delete.popup.title',
          content: 'pipeline.delete.popup.message',
          submit: {
            text: 'delete.label',
            func: async () => {
              const { status, message } = await deletePipeLines(id);
              if (status !== STATUS_SUCCESS) {
                toast.error(message);
              } else {
                await getPipelineMenu(workspaceId, setCardData);
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
    [dispatch, userName, workspaceId],
  );

  useEffect(() => {
    loadModalComponent('AI_PIPELINE_ADD');

    breadCrumbHandler(dispatch);
    getPipelineMenu(workspaceId, setCardData);
  }, [dispatch, handelRefresh, workspaceId]);

  return (
    <div className={cx('pipeline-menu-cont')}>
      <h1 className={cx('title')}>AI 파이프라인 프로젝트</h1>
      <CardList>
        <CreateCard
          label={'새 프로젝트 생성'}
          handleCreateCard={handleCreateCard}
          height={397}
        />
        {cardData.map((cardInfo, idx) => {
          const {
            id,
            title,
            subTitle,
            constructor,
            updateTime,
            createTime,
            runningTime,
            isAccess,
            status,
            isBookMark,
            private_user_list,
          } = cardInfo;
          return (
            <CardItem
              key={id ?? idx}
              id={id}
              title={title}
              subTitle={subTitle}
              constructor={constructor}
              updateTime={updateTime}
              createTime={createTime}
              runningTime={runningTime}
              status={status}
              isAccess={isAccess}
              isBookMark={isBookMark}
              private_user_list={private_user_list}
              handleBookMark={handleBookMark}
              handleOnClickCard={handleOnClickCard}
              handleDelete={handleDelete}
              handleEdit={handleEdit}
            />
          );
        })}
      </CardList>
    </div>
  );
}
