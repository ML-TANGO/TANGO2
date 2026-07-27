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

// 배포 유형(playground.deploy_type) → 유형 라벨 칩(상태 배지 옆). 3종 모두 playground row.
const TYPE_LABEL = {
  cluster: '클러스터',
  edge: '온디바이스',
  standalone: 'Standalone',
};

// 배포 유형별 상세 라우팅 경로.
const detailPath = (wid, kind, id) => {
  if (kind === 'edge') return `/user/workspace/${wid}/edge-deploy/${id}`;
  if (kind === 'standalone')
    return `/user/workspace/${wid}/standalone-deploy/${id}`;
  return `/user/workspace/${wid}/llmplayground/${id}/llmplayground`;
};

const breadCrumbHandler = (dispatch) => {
  dispatch(
    startPath([
      {
        component: {
          // D6 v3: Playground → "배포" 탭 repurpose (라벨 일관성)
          name: 'Deployment',
        },
      },
    ]),
  );
};

// 배포 목록 — getPlayground(cluster/edge/standalone 모두 playground row) 기반.
//   각 행에 deploy_type + access/owner/bookmark/users 가 있어 유형 배지·접근가드·북마크를 모두 지원.
const getPlaygroundInfo = async (workspace_id, setDeployItems) => {
  const { result, message, status, error } = await getPlayground(workspace_id);
  if (status === STATUS_SUCCESS) {
    const list = (result || []).map((r) => {
      const kind = r.deploy_type || 'cluster';
      return {
        id: r.id,
        kind,
        title: r.name,
        typeBadge: TYPE_LABEL[kind] || kind,
        subTitle: r.description,
        constructor: r.owner,
        updateTime: r.update_datetime,
        createTime: r.create_datetime,
        isBookMark: r.bookmark,
        isAccess: r.access,
        userList: r.users,
        status: r.status,
        // 이중모델 세션 판별(라우팅용) — mode==='dual' 이면 /dual-deploy 상세로.
        mode: r.mode,
      };
    });
    const sortArr = list.sort((a, b) => b.isBookMark - a.isBookMark);
    setDeployItems(sortArr);
    return sortArr;
  }
  errorToastMessage(error, message);
  return [];
};

const PlaygroundMenu = () => {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const dispatch = useDispatch();
  const history = useHistory();
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const { id: workspace_id } = match.params;

  const [deployItems, setDeployItems] = useState([]);

  // D6 v3: "+새 배포" → 플랫폼 표준 모달(NewDeploymentModal, 수정 플로우와 대칭).
  //   cluster/edge/standalone 모두 생성 진행. 생성 후 유형별 상세로 이동.
  const handleCreateCard = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'NEW_DEPLOYMENT',
        modalData: {
          workspace_id,
          handleRefresh: () => getPlaygroundInfo(workspace_id, setDeployItems),
        },
      }),
    );
  }, [dispatch, workspace_id]);

  // private(access===0) 배포는 소유자/지정 사용자만 조작 — UI 접근가드(BE authZ 비활성 하 유일 방어선).
  const hasAccess = useCallback(
    (isAccess, constructor, userList) => {
      if (isAccess !== 0) return true;
      if (userName === constructor) return true;
      return !!(userList || []).find(({ user_name }) => user_name === userName);
    },
    [userName],
  );

  // 카드 클릭 → 접근가드 후 배포 유형별 상세 라우팅.
  const handleOnClickCard = useCallback(
    (e, id, constructor, isAccess, userList) => {
      e.stopPropagation();
      if (!hasAccess(isAccess, constructor, userList)) {
        toast.error('접근 권한이 없습니다.');
        return;
      }
      const item = deployItems.find((i) => String(i.id) === String(id));
      // 이중모델 세션 → 배포측 이중 상세(구성/배포). 상세가 프로비저닝 여부에 따라 추론으로 리다이렉트.
      if (item?.mode === 'dual') {
        history.push(`/user/workspace/${workspace_id}/dual-deploy/${id}`);
        return;
      }
      history.push(detailPath(workspace_id, item?.kind, id));
    },
    [history, workspace_id, deployItems, hasAccess],
  );

  const handleDelete = useCallback(
    async (e, id, title, isAccess, userList, constructor) => {
      e.stopPropagation();
      if (!hasAccess(isAccess, constructor, userList)) {
        toast.error('접근 권한이 없습니다.');
        return;
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
                await getPlaygroundInfo(workspace_id, setDeployItems);
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
    [dispatch, workspace_id, hasAccess],
  );

  const handleBookMark = useCallback(
    async (e, id, isBookMark) => {
      e.stopPropagation();
      if (!isBookMark) {
        await postBookmark(id);
      } else {
        await deletePlaygroundBookmark(id);
      }
      await getPlaygroundInfo(workspace_id, setDeployItems);
    },
    [workspace_id],
  );

  const handleEdit = useCallback(
    async (e, id, isAccess, userList, constructor) => {
      e.stopPropagation();
      if (!hasAccess(isAccess, constructor, userList)) {
        toast.error('접근 권한이 없습니다.');
        return;
      }
      const playground_data = (
        await getPlaygroundInfo(workspace_id, setDeployItems)
      ).find((item) => String(item.id) === String(id));
      const transformUserList = (playground_data?.userList || []).map(
        (info) => ({
          label: info.user_name,
          value: info.user_id,
        }),
      );
      dispatch(
        openModal({
          modalType: 'EDIT_PLAYGROUND',
          modalData: {
            workspace_id,
            userList: transformUserList,
            playground_data,
            isAccess: playground_data?.isAccess,
            handleRefresh: async () =>
              await getPlaygroundInfo(workspace_id, setDeployItems),
          },
        }),
      );
    },
    [dispatch, workspace_id, hasAccess],
  );

  useEffect(() => {
    loadModalComponent('EDIT_PLAYGROUND');
    loadModalComponent('NEW_DEPLOYMENT');

    breadCrumbHandler(dispatch);
    getPlaygroundInfo(workspace_id, setDeployItems);
  }, [dispatch, workspace_id]);

  return (
    <div className={cx('playground-cont')}>
      {/* D6 v3: 배포 목록 = cluster(클러스터) + edge(온디바이스) + standalone (모두 playground row, deploy_type 구분) */}
      <h1 className={cx('title')}>{t('Deployment')}</h1>
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
          cardItems={deployItems}
          statusBadge
        />
      </Suspense>
    </div>
  );
};

export default PlaygroundMenu;
