import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import EvalProjectCreateModal from './EvalProjectCreateModal';

import { deleteEvalProject, listEvalProjects } from '@src/apis/llm/evaluation';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
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
};

const fmtDate = (v) => (v ? String(v).replace('T', ' ').slice(0, 16) : '-');

// 평가 프로젝트 목록 = 평가 표면의 랜딩(구 4카드 허브 대체, 설계 §6).
//   프로젝트 행 = 이름·유형뱃지·모델·데이터셋수·상태칩·생성자·생성일. "새 프로젝트" → 생성 모달,
//   행 클릭 → 상세 라우트. 삭제는 확인 후 FK CASCADE(BE). model 이름은 1회 models 조회로 매핑.
const EvaluationMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [projects, setProjects] = useState(null); // null=로딩, []=빈 상태
  const [modelNames, setModelNames] = useState({}); // model_id → name
  const [showCreate, setShowCreate] = useState(false);

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

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    fetchProjects();
    fetchModelNames();
  }, [dispatch, fetchProjects, fetchModelNames]);

  const openDetail = (p) =>
    history.push(`/user/workspace/${workspaceId}/evaluation/project/${p.id}`);

  const handleDelete = (p, e) => {
    e.stopPropagation();
    dispatch(
      openConfirm({
        title: 'evaluation.project.delete.title',
        content: 'evaluation.project.delete.message',
        testid: 'eval-project-delete-modal',
        submit: {
          text: 'delete.label',
          func: async () => {
            const res = await deleteEvalProject(p.id);
            if (res.status !== STATUS_SUCCESS) {
              errorToastMessage(res.error, res.message);
              return;
            }
            await fetchProjects();
          },
        },
        cancel: { text: 'cancel.label' },
        confirmMessage: p.name,
      }),
    );
  };

  // 생성 성공 → 상세로 이동(get_project shape 는 { project } 또는 flat 방어).
  const handleCreated = (result) => {
    setShowCreate(false);
    const pid = result?.project?.id ?? result?.id;
    if (pid != null) {
      history.push(`/user/workspace/${workspaceId}/evaluation/project/${pid}`);
    } else {
      fetchProjects();
    }
  };

  return (
    <div className={cx('eval-projects')}>
      <div className={cx('head')}>
        <div className={cx('head-text')}>
          <h1 className={cx('title')}>{t('evaluation.project.title')}</h1>
          <p className={cx('subtitle')}>{t('evaluation.project.subtitle')}</p>
        </div>
        <button
          type='button'
          className={cx('new-btn')}
          onClick={() => setShowCreate(true)}
        >
          + {t('evaluation.project.new')}
        </button>
      </div>

      {projects === null ? (
        <div className={cx('placeholder')}>
          {t('evaluation.project.loading')}
        </div>
      ) : projects.length === 0 ? (
        <div className={cx('empty')}>
          <p className={cx('empty-text')}>{t('evaluation.project.empty')}</p>
          <button
            type='button'
            className={cx('new-btn')}
            onClick={() => setShowCreate(true)}
          >
            + {t('evaluation.project.new')}
          </button>
        </div>
      ) : (
        <div className={cx('project-list')}>
          {projects.map((p) => (
            <div
              key={p.id}
              className={cx('project-card')}
              onClick={() => openDetail(p)}
            >
              <div className={cx('card-main')}>
                <div className={cx('card-name-row')}>
                  <span className={cx('card-name')}>{p.name}</span>
                  <span className={cx('type-badge', `type-${p.eval_type}`)}>
                    {t(TYPE_KEYS[p.eval_type] || p.eval_type)}
                  </span>
                </div>
                <div className={cx('card-meta')}>
                  <span className={cx('meta-item')}>
                    {t('evaluation.project.model')}:{' '}
                    {modelNames[p.model_id] || `#${p.model_id}`}
                  </span>
                  <span className={cx('meta-sep')}>·</span>
                  <span className={cx('meta-item')}>
                    {t('evaluation.project.datasetCount', {
                      n: (p.dataset_ids || []).length,
                    })}
                  </span>
                  {p.creator && (
                    <>
                      <span className={cx('meta-sep')}>·</span>
                      <span className={cx('meta-item')}>{p.creator}</span>
                    </>
                  )}
                </div>
              </div>
              <div className={cx('card-side')}>
                <span className={cx('status-chip', `status-${p.status}`)}>
                  {t(STATUS_KEYS[p.status] || p.status)}
                </span>
                <span className={cx('card-date')}>
                  {fmtDate(p.create_datetime)}
                </span>
                <button
                  type='button'
                  className={cx('del-btn')}
                  title={t('delete.label')}
                  onClick={(e) => handleDelete(p, e)}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <EvalProjectCreateModal
          workspaceId={workspaceId}
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
};

export default EvaluationMenu;
