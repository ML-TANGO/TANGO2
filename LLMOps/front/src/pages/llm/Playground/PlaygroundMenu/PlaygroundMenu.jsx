import { Suspense, useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import CardTemplate from '@src/components/molecules/CardTemplate/CardTemplate';

import {
  deletePlayground,
  deletePlaygroundBookmark,
  getPlayground,
  postBookmark,
} from '@src/apis/llm/playground';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './PlaygroundMenu.module.scss';

const cx = classNames.bind(style);

const breadCrumbHandler = (dispatch) => {
  dispatch(
    startPath([
      {
        component: {
          name: 'playground',
        },
      },
    ]),
  );
};

const getPlaygroundInfo = async (workspace_id, setPlaygroundInfo) => {
  const { result, message, status, error } = await getPlayground(workspace_id);
  if (status === STATUS_SUCCESS) {
    const transformList = result.map((el) => {
      const {
        id,
        name,
        description,
        owner,
        update_datetime,
        create_datetime,
        bookmark,
        access,
        status,
        users,
      } = el;
      return {
        id,
        title: name,
        subTitle: description,
        constructor: owner,
        updateTime: update_datetime,
        createTime: create_datetime,
        isBookMark: bookmark,
        isAccess: access,
        userList: users,
        status,
      };
    });
    const sortArr = transformList.sort((a, b) => b.isBookMark - a.isBookMark);
    setPlaygroundInfo(sortArr);
    return transformList;
  } else {
    errorToastMessage(error, message);
  }
};

const PlaygroundMenu = () => {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const dispatch = useDispatch();
  const history = useHistory();
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const { id: workspace_id } = match.params;

  const [playgroundInfo, setPlaygroundInfo] = useState([]);

  const handleCreateCard = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'ADD_PLAYGROUND',
        modalData: {
          workspace_id,
          handleRefresh: async () =>
            await getPlaygroundInfo(workspace_id, setPlaygroundInfo),
        },
      }),
    );
  }, [dispatch, workspace_id]);

  const handleOnClickCard = useCallback(
    (e, id, constructor, isAccess, userList) => {
      e.stopPropagation();

      if (isAccess === 0) {
        if (userName !== constructor) {
          const isEditAccess = userList.find(
            ({ user_name }) => user_name === userName,
          );
          if (!isEditAccess) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }
      history.push(
        `/user/workspace/${workspace_id}/llmplayground/${id}/llmplayground`,
      );
    },
    [userName, history, workspace_id],
  );

  const handleDelete = useCallback(
    async (e, id, title, isAccess, userList, constructor) => {
      e.stopPropagation();

      if (isAccess === 0) {
        if (userName !== constructor) {
          const isEditAccess = userList.find(
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
          title: 'playground.delete.label',
          content: 'playground.delete.message',
          testid: 'training-delete-modal',
          submit: {
            text: 'delete.label',
            func: async () => {
              const { status, message } = await deletePlayground(id);
              if (status !== STATUS_SUCCESS) {
                toast.error(message);
              } else {
                await getPlaygroundInfo(workspace_id, setPlaygroundInfo);
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
        await postBookmark(id);
      } else {
        await deletePlaygroundBookmark(id);
      }
      await getPlaygroundInfo(workspace_id, setPlaygroundInfo);
    },
    [workspace_id],
  );

  const handleEdit = useCallback(
    async (e, id, isAccess, userList, constructor) => {
      e.stopPropagation();

      if (isAccess === 0) {
        if (userName !== constructor) {
          const isEditAccess = userList.find(
            ({ user_name }) => user_name === userName,
          );
          if (!isEditAccess) {
            toast.error('접근 권한이 없습니다.');
            return;
          }
        }
      }

      const playground_data = await getPlaygroundInfo(
        workspace_id,
        setPlaygroundInfo,
      ).then((res) => res.find((item) => item.id === id));

      const transformUserList = userList.map((info) => {
        return {
          label: info.user_name,
          value: info.user_id,
        };
      });

      dispatch(
        openModal({
          modalType: 'EDIT_PLAYGROUND',
          modalData: {
            workspace_id,
            userList: transformUserList,
            playground_data,
            isAccess,
            handleRefresh: async () =>
              await getPlaygroundInfo(workspace_id, setPlaygroundInfo),
          },
        }),
      );
    },
    [dispatch, userName, workspace_id],
  );

  useEffect(() => {
    loadModalComponent('ADD_PLAYGROUND');
    loadModalComponent('EDIT_PLAYGROUND');

    breadCrumbHandler(dispatch);
    getPlaygroundInfo(workspace_id, setPlaygroundInfo);
  }, [dispatch, workspace_id]);

  return (
    <div className={cx('playground-cont')}>
      <h1 className={cx('title')}>{t('playground.label')}</h1>
      <Suspense fallback={<>loading...</>}>
        <CardTemplate
          createLabel={t('playground.add.label')}
          handleDelete={handleDelete}
          handleCreateCard={handleCreateCard}
          handleBookMark={(e, id, isBookMark) =>
            handleBookMark(e, id, isBookMark)
          }
          handleEdit={handleEdit}
          handleOnClickCard={handleOnClickCard}
          cardItems={playgroundInfo}
        />
      </Suspense>
    </div>
  );
};

export default PlaygroundMenu;
