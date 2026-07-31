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
   * Model 목록 가져오기
   */
  const getModels = useCallback(async () => {
    const { status, result, message, error } = await getModel(workspaceId);
    if (status === STATUS_SUCCESS) {
      if (result) {
        const newModels = result.map((v) => {
          // 카드 타입 칩: 멀티모달(내부 VLM=load_type / 도메인 SDS=domain) vs 단일(single).
          // training_type='external' 자체로 판별하지 않음 — 추후 SDM/SDF 도 external 이라 오분류 방지.
          const kind =
            v.load_type === 'multimodal' || v.domain === 'SDS'
              ? 'multimodal'
              : 'single';
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
            kind,
            typeBadge: kind,
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

      // 진입/수정 모두 BE is_access 단일 판정 사용 (관리자 OR 소유자 OR 모델 멤버).
      // 이전엔 여기서 userName/userList 로 규칙을 재구현해 BE 게이트와 어긋났다.
      if (isAccess === 0) {
        toast.error('접근 권한이 없습니다.');
        return;
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
  const modelDelete = (e, id, title, isAccess) => {
    e.stopPropagation();

    // 진입/수정과 같은 BE is_access 단일 판정을 삭제에도 적용한다. Card 는 접근 불가 카드의
    // 버튼을 pointer-events 로만 막아 키보드(Tab+Enter)로는 여전히 도달하므로, 핸들러에서
    // 막지 않으면 접근 권한 없는 모델을 지울 수 있다. (BE DELETE /models 의 authZ 부재는
    // 플랫폼 posture 차원 과제 — 이 가드는 UI 오조작 차단이며 보안 경계가 아니다.)
    if (isAccess === 0) {
      toast.error('접근 권한이 없습니다.');
      return;
    }

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
    // 목록 카드는 계속 노출하되 상세 진입만 차단(제품 규칙 2026-07-27).
    // 판정은 BE 가 내려준 is_access 하나만 신뢰 — 규칙(관리자 OR 소유자 OR 모델 멤버)은
    // BE user_can_access_model / get_models 의 is_access 에 단일 정의돼 있다.
    if (isAccess === 0) {
      toast.error('접근 권한이 없습니다.');
      return;
    }

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
        // 접근 불가 모델(관리자·소유자·멤버 아님)은 카드는 보이되 회색+클릭불가.
        // is_access 는 BE 가 정본 규칙으로 계산해 내려준다(user_can_access_model 과 동일).
        disableNoAccess
      />
    </div>
  );
}

export default Model;
