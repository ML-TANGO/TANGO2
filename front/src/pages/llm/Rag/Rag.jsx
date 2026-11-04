import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import CardTemplate from '@src/components/molecules/CardTemplate/CardTemplate';
// CSS module
import { toast } from '@src/components/Toast';

import {
  deleteRag,
  deleteRagBookmark,
  getRag,
  postRagBookmark,
  putRagDescription,
} from '@src/apis/llm/rag';
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
import style from './Rag.module.scss';

const cx = classNames.bind(style);

function Rag() {
  // Router Hooks
  const history = useHistory();
  const { id: workspaceId } = useParams();

  // State
  const [ragData, setRagData] = useState([]);

  const { t } = useTranslation();
  const dispatch = useDispatch();

  const handleCreateCard = () => {
    dispatch(
      openModal({
        modalType: 'ADD_RAG',
        modalData: {
          workspaceId,
          refresh: () => getRags(),
        },
      }),
    );
  };

  const handleBookMark = async (e, ragId, isBookMark) => {
    e.stopPropagation();
    if (!isBookMark) {
      await postRagBookmark({ ragId });
    } else {
      await deleteRagBookmark({ ragId });
    }
    await getRags();
  };
  /**
   * API 호출 GET
   * Model 목록 가져오기
   */
  const getRags = useCallback(async () => {
    const { status, result, message, error } = await getRag(workspaceId);
    if (status === STATUS_SUCCESS) {
      if (result) {
        setRagData((prevModels) => {
          const newModels = result.map((v) => {
            return {
              ...v,
              createTime: v.create_datetime,
              updateTime: v.update_datetime,
              constructor: v.owner,
              title: v.name,
              subTitle: v.description,
              isBookMark: v.bookmark,
              isAccess: v.access,
              status: v.status,
            };
          });

          const hasChanges = newModels.some((newModel) => {
            const oldModel = prevModels.find((m) => m.id === newModel.id);
            return (
              !oldModel || JSON.stringify(oldModel) !== JSON.stringify(newModel)
            );
          });

          return hasChanges
            ? newModels.sort((a, b) => b.isBookMark - a.isBookMark)
            : prevModels;
        });
      }
      return true;
    } else {
      errorToastMessage(error, message);
      return false;
    }
  }, [workspaceId]);

  //* 수정
  const handleEdit = useCallback(
    async (e, id) => {
      e.stopPropagation();

      const { status, result, message, error } = await getRag(workspaceId);

      if (status === STATUS_SUCCESS) {
        const rag_item = result.find((info) => info.id === id);
        dispatch(
          openModal({
            modalType: 'EDIT_RAG',
            modalData: {
              workspaceId,
              rag_item,
              refresh: async () => {
                getRags();
              },
            },
          }),
        );
      } else {
        toast.error(message);
      }
    },
    [dispatch, getRags, workspaceId],
  );

  //* 삭제
  const onDelete = async (id) => {
    const response = await deleteRag({ ragId: [id] });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      getRags();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * rag 삭제
   */
  const modelDelete = (e, id, title) => {
    e.stopPropagation();

    dispatch(
      openConfirm({
        title: 'deleteModelPopup.title.label',
        content: 'deleteRagPopup.message',
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
   * 모델 상세 페이지(info)로 이동
   */
  const { userName } = useSelector((state) => state.auth, shallowEqual);
  const moveToRagDetail = (e, id, constructor, isAccess) => {
    e.stopPropagation();

    if (constructor !== userName && !isAccess) return;
    if (!e.target.closest('button') && !e.target.closest('.event-block')) {
      history.push(`/user/workspace/${workspaceId}/rag/${id}`);
    }
  };

  useEffect(() => {
    loadModalComponent('ADD_RAG');
    loadModalComponent('EDIT_RAG');

    breadCrumbHandler();
  }, [breadCrumbHandler]);

  useIntervalCall(getRags, 5000);

  return (
    <div className={cx('playground-cont')}>
      <h1 className={cx('title')}>RAG</h1>
      <CardTemplate
        createLabel={t('createRag.label')}
        cardItems={ragData}
        handleBookMark={(e, id, isBookMark) =>
          handleBookMark(e, id, isBookMark)
        }
        handleCreateCard={handleCreateCard}
        handleOnClickCard={moveToRagDetail}
        handleEdit={handleEdit}
        handleDelete={modelDelete}
      />
    </div>
  );
}

export default Rag;
