import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import CardTemplate from '@src/components/molecules/CardTemplate/CardTemplate';
import {
  deleteEvalProject,
  getEvalDatasets,
  listEvalProjects,
} from '@src/apis/llm/evaluation';
import { loadModalComponent } from '@src/modal';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EvaluationMenu.module.scss';

const cx = classNames.bind(style);

// 평가 유형/상태 → i18n 라벨 키 (프로젝트 목록·상세 공통).
const TYPE_KEYS = {
  benchmark: 'evaluation.project.type.benchmark',
  judge: 'evaluation.project.type.judge',
  expert: 'evaluation.project.type.expert',
};
const STATUS_KEYS = {
  created: 'evaluation.project.status.created',
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
  failed: 'evaluation.failed',
  error: 'evaluation.failed',
};

// 평가 프로젝트 목록 = 평가 표면의 랜딩(구 4카드 허브 대체, 설계 §6).
//   플랫폼 표준 CardTemplate 가 생성 타일·카드·유형/상태 배지·삭제 버튼을 소유한다.
//   카드 클릭 → 상세 라우트. 삭제는 확인 후 FK CASCADE(BE). model 이름은 1회 models 조회로 매핑.
const EvaluationMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [projects, setProjects] = useState(null); // null=로딩, []=빈 상태
  const [modelNames, setModelNames] = useState({}); // model_id → name
  const [datasetNames, setDatasetNames] = useState({}); // dataset_id → name

  const fetchProjects = useCallback(async () => {
    const res = await listEvalProjects(workspaceId);
    if (res.status === STATUS_SUCCESS) {
      setProjects(
        Array.isArray(res.result?.projects) ? res.result.projects : [],
      );
    } else {
      setProjects([]);
      errorToastMessage(res.error, res.message);
    }
  }, [workspaceId]);

  // 모델 id→이름 매핑(목록 표시용) — 1회 조회(cheap). 실패해도 목록은 model_id fallback.
  const fetchModelNames = useCallback(async () => {
    const res = await callApi({
      url: `models?workspace_id=${workspaceId}`,
      method: 'GET',
    });
    if (res.status !== STATUS_SUCCESS) return;
    const list = Array.isArray(res.result)
      ? res.result
      : (res.result?.list ?? []);
    const map = {};
    list.forEach((m) => {
      if (m?.id != null) map[m.id] = m.name;
    });
    setModelNames(map);
  }, [workspaceId]);

  // 데이터셋 id→이름 매핑(목록 표시용) — ProjectDetail 과 같은 워크스페이스 목록 1회 조회.
  const fetchDatasetNames = useCallback(async () => {
    const res = await getEvalDatasets(workspaceId);
    if (res.status !== STATUS_SUCCESS) return;
    const list = Array.isArray(res.result)
      ? res.result
      : (res.result?.list ?? []);
    const map = {};
    list.forEach((dataset) => {
      const id = dataset.id ?? dataset.dataset_id;
      const name = dataset.name ?? dataset.dataset_name;
      if (id != null && name) map[id] = name;
    });
    setDatasetNames(map);
  }, [workspaceId]);

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    loadModalComponent('CREATE_EVAL_PROJECT');
    fetchProjects();
    fetchModelNames();
  }, [dispatch, fetchProjects, fetchModelNames]);

  useEffect(() => {
    fetchDatasetNames();
  }, [fetchDatasetNames]);

  // Card 의 onClick 규약: (e, id, constructor, isAccess, userList)
  const openDetail = (e, id) => {
    e.stopPropagation();
    history.push(`/user/workspace/${workspaceId}/evaluation/project/${id}`);
  };

  const handleDelete = (e, id, title) => {
    e.stopPropagation();
    dispatch(
      openConfirm({
        title: 'evaluation.project.delete.title',
        content: 'evaluation.project.delete.message',
        testid: 'eval-project-delete-modal',
        submit: {
          text: 'delete.label',
          func: async () => {
            const res = await deleteEvalProject(id);
            if (res.status !== STATUS_SUCCESS) {
              errorToastMessage(res.error, res.message);
              return;
            }
            await fetchProjects();
          },
        },
        cancel: { text: 'cancel.label' },
        confirmMessage: title,
      }),
    );
  };

  // 생성 성공 → 상세로 이동(get_project shape 는 { project } 또는 flat 방어).
  const handleCreated = (result) => {
    const pid = result?.project?.id ?? result?.id;
    if (pid != null) {
      history.push(`/user/workspace/${workspaceId}/evaluation/project/${pid}`);
    } else {
      fetchProjects();
    }
  };

  // 생성 모달 열기 — 전역 Redux 모달 시스템(학습/배포 생성 모달과 동일 패턴).
  //   submit.func 로 생성 성공 결과를 받아 handleCreated 가 상세로 이동. 프레임이 닫기 담당.
  const openCreateModal = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_EVAL_PROJECT',
        modalData: {
          submit: { text: 'evaluation.project.create', func: handleCreated },
          cancel: { text: 'cancel.label' },
          workspaceId,
        },
      }),
    );
  };

  const cardItems = (projects ?? []).map((p) => {
    const isRunning = p.status === 'running';
    const isError = p.status === 'failed' || p.status === 'error';
    const datasetIds = Array.isArray(p.dataset_ids) ? p.dataset_ids : [];
    const resolvedDatasetNames = datasetIds
      .map((id) => datasetNames[id])
      .filter(Boolean);
    const hasAllDatasetNames =
      datasetIds.length > 0 &&
      resolvedDatasetNames.length === datasetIds.length;
    const datasetCountLabel = t('evaluation.project.datasetCount', {
      n: datasetIds.length,
    });
    const datasetLabel = hasAllDatasetNames
      ? resolvedDatasetNames.length === 1
        ? resolvedDatasetNames[0]
        : t('evaluation.project.datasetMore', {
            name: resolvedDatasetNames[0],
            n: resolvedDatasetNames.length - 1,
          })
      : datasetCountLabel;
    const datasetTitle = hasAllDatasetNames
      ? resolvedDatasetNames.join(', ')
      : datasetCountLabel;
    return {
      id: p.id,
      title: p.name,
      subTitle: (
        <>
          {`${t('evaluation.project.model')}: ${
            modelNames[p.model_id] || `#${p.model_id}`
          } · `}
          <span title={datasetTitle}>
            {`${t('evaluation.project.dataset')}: ${datasetLabel}`}
          </span>
          {' · '}
          <span
            className={cx(
              'card-status',
              isRunning && 'card-status-running',
              isError && 'card-status-error',
            )}
          >
            {t(STATUS_KEYS[p.status] || p.status)}
          </span>
        </>
      ),
      constructor: p.creator,
      createTime: p.create_datetime,
      updateTime: p.update_datetime,
      // 평가 프로젝트는 워크스페이스 단위 목록이며 별도 카드 접근 제한 필드가 없다.
      isAccess: 1,
      typeBadge: t(TYPE_KEYS[p.eval_type] || p.eval_type),
      kind: p.eval_type,
    };
  });

  return (
    <div className={cx('eval-projects')}>
      <div className={cx('title-bar')}>
        <h1 className={cx('title')}>{t('evaluation.project.title')}</h1>
      </div>

      {projects === null ? (
        <div className={cx('placeholder')}>
          {t('evaluation.project.loading')}
        </div>
      ) : (
        <CardTemplate
          createLabel={t('evaluation.project.new')}
          cardItems={cardItems}
          handleCreateCard={openCreateModal}
          handleOnClickCard={openDetail}
          handleDelete={handleDelete}
        />
      )}
    </div>
  );
};

export default EvaluationMenu;
