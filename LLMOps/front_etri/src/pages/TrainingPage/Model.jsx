import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import CardTemplate from '@src/components/molecules/CardTemplate/CardTemplate';
// CSS module
import { toast } from '@src/components/Toast';

import { getModel } from '@src/apis/llm/model';
import { startPath } from '@src/store/modules/breadCrumb';
import { closeConfirm, openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
// Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './Model.module.scss';

const cx = classNames.bind(style);

function Model() {
  // Router Hooks
  const history = useHistory();
  const { id: workspaceId } = useParams();

  const { userName } = useSelector((state) => state.auth, shallowEqual);

  // State
  const [models, setModels] = useState([]);

  const { t } = useTranslation();
  const dispatch = useDispatch();

  const handleCreateCard = () => {
    dispatch(
      openModal({
        modalType: 'ADD_MODEL',
        modalData: {
          workspaceId,
          refresh: () => getModels(),
        },
      }),
    );
  };

  const breadCrumbHandler = useCallback(() => {
    dispatch(
      startPath([
        {
          component: {
            name: 'model',
          },
        },
      ]),
    );
  }, [dispatch]);

  /**
   * API 호출 GET
   * TrainingPage 목록 가져오기
   */
  const getModels = useCallback(async () => {
    const { status, result, message, error } = await getModel(workspaceId);
    if (status === STATUS_SUCCESS) {
      if (result) {
        const newModels = result.map((v) => {
          return {
            ...v,
            createTime: v.create_datetime,
            updateTime: v.update_datetime,
            title: v.name,
            constructor: v.create_user_name,
            subTitle: v.description,
            isBookMark: v.bookmark,
            isAccess: v.is_access ? 1 : 0,
            status: v.status?.fine_tuning === 'running' ? 'active' : null,
            userList: v?.users,
          };
        });
        setModels((prevModels) => {
          const hasChanges =
            prevModels.length !== newModels.length ||
            newModels.some((newModel) => {
              const oldModel = prevModels.find((m) => m.id === newModel.id);
              return (
                !oldModel ||
                JSON.stringify(oldModel) !== JSON.stringify(newModel)
              );
            });

          return hasChanges
            ? newModels.sort((a, b) => b.isBookMark - a.isBookMark)
            : prevModels;
        });

        return newModels;
      }
      // return true;
    } else {
      errorToastMessage(error, message);
      return false;
    }
  }, [workspaceId]);

  const onDelete = async (id) => {
    const response = await callApi({
      // 현재 int로 받음 -> array로 바꿔달라고 요청
      url: `models?model_id=${id}`,
      method: 'delete',
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      getModels();
    } else {
      errorToastMessage(error, message);
    }
  };

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

      const prevModelData = await getModels().then((res) =>
        res.find((item) => item.id === id),
      );

      const transformUserList = userList.map((info) => {
        return {
          label: info.user_name,
          value: info.user_id,
        };
      });

      dispatch(
        openModal({
          modalType: 'EDIT_MODEL',
          modalData: {
            workspaceId,
            userList: transformUserList,
            prevModelData,
            isAccess,
            handleRefresh: async () => await getModels(),
          },
        }),
      );
    },
    [dispatch, getModels, userName, workspaceId],
  );

  /**
   * 모델 삭제
   */
  const modelDelete = (e, id, title) => {
    e.stopPropagation();

    dispatch(
      openConfirm({
        title: 'deleteModelPopup.title.label',
        content: 'deleteModelPopup.message',
        testid: 'model-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            // onDelete(trainingId);
            onDelete(id);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: title,
      }),
    );
  };

  const postBookMark = async (modelId) => {
    const res = await callApi({
      url: 'models/bookmark',
      method: 'put',
      body: modelId,
    });
    return res;
  };

  const handleBookMark = async (e, id, isBookMark) => {
    e.stopPropagation();
    if (!isBookMark) {
      await postBookMark(id);
    } else {
      await postBookMark(id);
    }
    await getModels();
  };

  /**
   * 모델 상세 페이지(info)로 이동
   */

  const moveToModelDetail = (e, id, constructor, isAccess) => {
    e.stopPropagation();
    // if (isAccess === 0 && userName !== constructor) return;

    history.push(`/user/workspace/${workspaceId}/model/${id}/info`);
    // if (!e.target.closest('button') && !e.target.closest('.event-block')) {
    // }
  };

  useEffect(() => {
    loadModalComponent('ADD_MODEL');
    loadModalComponent('EDIT_MODEL');
    loadModalComponent('HUGGINGFACE_TOKEN_MODAL');
    breadCrumbHandler();
  }, [breadCrumbHandler]);

  useEffect(() => {
    getModels();
  }, [getModels]);

  // useIntervalCall(getModels, 5000);

  return (
    <div className={cx('playground-cont')}>
      <h1 className={cx('title')}>{t('model.label')}</h1>
      <CardTemplate
        createLabel={t('createModel.label')}
        cardItems={models}
        handleCreateCard={handleCreateCard}
        handleBookMark={(e, id, isBookMark) =>
          handleBookMark(e, id, isBookMark)
        }
        handleEdit={handleEdit}
        handleOnClickCard={moveToModelDetail}
        handleDelete={modelDelete}
      />
    </div>
  );
}

export default Model;
