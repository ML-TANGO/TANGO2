import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import CardTemplate from '@src/components/molecules/CardTemplate/CardTemplate';
import { deleteEvalProject, listEvalProjects } from '@src/apis/llm/evaluation';
import { loadModalComponent } from '@src/modal';
import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

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
  intent: 'evaluation.project.type.intent',
};

// 카드 메타행 상태 배지의 라벨/색. 라벨은 배지에 들어갈 **짧은 말**이어야 한다 —
// 종전 failed 가 문장 키(evaluation.failed = "평가에 실패했습니다.")를 써서 배지가 한 줄을
// 통째로 먹었다.
const STATUS_KEYS = {
  created: 'evaluation.project.status.created',
  running: 'evaluation.project.status.running',
  completed: 'evaluation.project.status.completed',
  failed: 'evaluation.project.status.failed',
  error: 'evaluation.project.status.failed',
};

// Card 의 status-badge 색 modifier. 회색(대기) → 초록(살아 있음) → 파랑(끝남) / 빨강(실패).
const STATUS_BADGE_KINDS = {
  created: 'stopped',
  running: 'running',
  completed: 'completed',
  failed: 'error',
  error: 'error',
};

// 평가 프로젝트 목록 = 평가 표면의 랜딩(구 4카드 허브 대체, 설계 §6).
//   플랫폼 표준 CardTemplate 가 생성 타일·카드·유형/상태 배지·삭제 버튼을 소유한다.
//   카드 클릭 → 상세 라우트. 삭제는 확인 후 FK CASCADE(BE). 수정은 설명만 여는 EDIT 모달.
const EvaluationMenu = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const [projects, setProjects] = useState(null); // null=로딩, []=빈 상태

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

  useEffect(() => {
    dispatch(startPath([{ component: { name: 'Evaluation' } }]));
    loadModalComponent('CREATE_EVAL_PROJECT');
    loadModalComponent('EDIT_EVAL_PROJECT');
    fetchProjects();
  }, [dispatch, fetchProjects]);

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

  // 수정 모달 열기 — 모델·배포 목록의 수정 아이콘과 같은 관행(EDIT_* 모달)이다.
  //   프로젝트에서 고칠 수 있는 건 **설명뿐**이라(이름·유형은 생성 후 불변) 모달도 설명만 연다.
  //   저장 응답은 프로젝트 전체가 아니라 { project_id, updated, description } 이므로
  //   목록을 다시 부른다(apis/llm/evaluation 의 updateEvalProject 주석 참조).
  const handleEdit = (e, id) => {
    e.stopPropagation();
    const project = (projects ?? []).find((p) => p.id === id);
    if (!project) return;
    dispatch(
      openModal({
        modalType: 'EDIT_EVAL_PROJECT',
        modalData: {
          submit: { text: 'update.label', func: () => fetchProjects() },
          cancel: { text: 'cancel.label' },
          workspaceId,
          project,
        },
      }),
    );
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
  const visibleProjects = projects ?? [];

  const cardItems = visibleProjects.map((p) => {
    const isRunning = p.status === 'running';
    return {
      id: p.id,
      title: p.name,
      // 본문 = 설명. 모델·배포 카드와 **같은 슬롯**이다. 비면 Card 가 공용
      // 플레이스홀더(no.desc, 회색)를 그리므로 여기서 대체 문구를 만들지 않는다.
      //   종전엔 여기에 "모델: X · 데이터셋: Y · 상태" 를 평문으로 넣어 설명 자리를 먹었다.
      //   모델·데이터셋은 이제 프로젝트가 아니라 **런이** 고르는 값이라(옛 프로젝트만
      //   잠긴 값을 가짐) 카드가 아니라 상세의 프로젝트 정보에서 읽는 것이 맞다.
      subTitle: p.description,
      constructor: p.creator,
      createTime: p.create_datetime,
      updateTime: p.update_datetime,
      // 평가 프로젝트는 워크스페이스 단위 목록이며 별도 카드 접근 제한 필드가 없다.
      isAccess: 1,
      // 실행 중 카드 강조 — 모델 목록이 학습 running 에 쓰는 것과 **같은 프롭**이다
      // (Model.jsx: status: fine_tuning === 'running' ? 'active' : null).
      // Card 가 status && status !== 'stop' 일 때 .active 를 붙인다.
      status: isRunning ? 'active' : null,
      // 상태는 메타행 배지로 — 배포 카드의 ● Running 과 같은 자리·같은 모양이다.
      //   status 프롭은 위에서 강조 전용('active')으로 쓰므로 라벨/색을 따로 넘긴다.
      statusBadgeLabel: t(STATUS_KEYS[p.status] || p.status),
      statusBadgeKind: STATUS_BADGE_KINDS[p.status] || 'stopped',
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
          handleEdit={handleEdit}
        />
      )}
    </div>
  );
};

export default EvaluationMenu;
