import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { ButtonV2 } from '@jonathan/ui-react';

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
import { moveRovingFocus } from '@src/utils/a11y';

import classNames from 'classnames/bind';
import style from './EvaluationMenu.module.scss';

const cx = classNames.bind(style);

// 평가 유형/상태 → i18n 라벨 키 (프로젝트 목록·상세 공통).
// 유형은 **채점 주체**로 가른다 — 기계가 정답과 대조하나(reference), 다른 LLM 이
// 판단하나(judge), 사람이 보나(expert). 종전 'benchmark' 는 앞의 둘이 섞여 있어
// 같은 유형 안에서 점수의 의미(0~1 정답률 vs 1~10 심판 점수)가 달랐다.
const TYPE_KEYS = {
  reference: 'evaluation.project.type.reference',
  judge: 'evaluation.project.type.judge',
  expert: 'evaluation.project.type.expert',
};

// 필터 탭 순서 — 'all' 은 유형이 아니라 해제 상태다.
const TYPE_FILTERS = ['all', 'reference', 'judge', 'expert'];
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
  const [typeFilter, setTypeFilter] = useState('all'); // 'all' | 유형
  // 유형 필터 탭 묶음 참조 — 방향키 이동은 공용 moveRovingFocus 가 담당한다.
  const filterGroupRef = useRef(null);
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

  const openCompare = () => {
    history.push(`/user/workspace/${workspaceId}/evaluation/compare`);
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

  // 유형별 개수 — 필터 탭에 그대로 실린다. 0 건인 유형도 탭을 지우지 않는다:
  // 개수가 0 이라는 사실 자체가 "이 유형으로는 아직 안 재 봤다"는 정보다.
  const typeCounts = useMemo(() => {
    const list = projects ?? [];
    const counts = { all: list.length };
    TYPE_FILTERS.filter((key) => key !== 'all').forEach((key) => {
      counts[key] = list.filter((p) => p.eval_type === key).length;
    });
    return counts;
  }, [projects]);

  const visibleProjects = (projects ?? []).filter(
    (p) => typeFilter === 'all' || p.eval_type === typeFilter,
  );

  const cardItems = visibleProjects.map((p) => {
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
    // 프로젝트는 이제 이름·유형만 잠근다 — 모델·데이터셋은 런마다 고른다. 옛 프로젝트만
    // 잠긴 값을 갖고 있으므로 **있을 때만** 세운다(없는 값을 '#undefined' 로 찍지 않는다).
    const metaParts = [];
    if (p.model_id != null) {
      metaParts.push(
        `${t('evaluation.project.model')}: ${
          modelNames[p.model_id] || `#${p.model_id}`
        }`,
      );
    }
    if (datasetIds.length > 0) {
      metaParts.push(`${t('evaluation.project.dataset')}: ${datasetLabel}`);
    }
    return {
      id: p.id,
      title: p.name,
      subTitle: (
        <>
          {metaParts.length > 0 && `${metaParts.join(' · ')} · `}
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
        {/* 교차 모델 비교는 프로젝트를 가로지르므로 프로젝트 상세가 아니라 허브에 둔다.
            화면·API·라우트는 이미 있고 이 링크만 없어 URL 직접 입력 외엔 도달 불가였다. */}
        <ButtonV2
          type='outline'
          size='l'
          label={t('evaluation.compare.open')}
          onClick={openCompare}
        />
      </div>

      {/* 유형 필터 — 프로젝트가 유형별로 다른 것을 재므로, 무엇을 재 왔는지가 목록의
          첫 질문이다. 개수를 라벨에 함께 실어 필터를 열기 전에도 분포가 보이게 한다. */}
      {projects !== null && (
        <div
          ref={filterGroupRef}
          className={cx('type-filter')}
          role='tablist'
          aria-label={t('evaluation.project.selectType')}
          onKeyDown={moveRovingFocus(
            filterGroupRef,
            TYPE_FILTERS,
            typeFilter,
            setTypeFilter,
          )}
        >
          {TYPE_FILTERS.map((key) => (
            <button
              key={key}
              type='button'
              role='tab'
              aria-selected={typeFilter === key}
              data-value={key}
              // roving tabIndex — 탭 묶음은 Tab 진입점이 하나여야 한다(고른 칩).
              // 안쪽 이동은 방향키가 맡는다(WAI-ARIA tablist).
              tabIndex={typeFilter === key ? 0 : -1}
              className={cx('type-chip', typeFilter === key && 'on')}
              onClick={() => setTypeFilter(key)}
            >
              {key === 'all'
                ? t('evaluation.project.filterAll')
                : t(TYPE_KEYS[key])}
              <span className={cx('type-count')}>{typeCounts[key] ?? 0}</span>
            </button>
          ))}
        </div>
      )}

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
