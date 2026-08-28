import { useState } from 'react';

import EvalProjectFormModal from '@src/components/Modal/EvalProjectFormModal';

import {
  createEvalProject,
  updateEvalProject,
} from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

// 평가 프로젝트 생성/수정 모달 컨테이너(스마트) — Redux 모달 시스템 편입.
//   data(=modalData) = { submit:{text,func}, cancel:{text}, workspaceId, project? }.
//   type = 'CREATE_EVAL_PROJECT' | 'EDIT_EVAL_PROJECT' — 학습/배포 모달과 같이 한 컨테이너가
//   두 모달 타입을 겸한다(modal.js 에서 둘 다 이 파일로 매핑).
//   프로젝트가 잠그는 것은 **이름과 평가 유형뿐**이다 — 모델·데이터셋은 런을 실행할 때 고른다.
//   생성 시점에 모델을 잠그면 한 프로젝트 안에서 모델을 견줄 수 없어(프로젝트 = 모델 1개)
//   "무엇을 평가하나"가 아니라 "어느 모델의 폴더인가"가 되어 버린다.
//   수정 모드에서 열려 있는 필드는 **설명뿐**이다 — 이름·유형은 생성 후 불변이고
//   BE 가 신설 중인 수정 엔드포인트도 description 만 받는다(apis/llm/evaluation 주석 참조).
//   생성 성공 시 data.submit.func(get_project) 로 부모(EvaluationMenu)가 상세로 이동, true 반환 → 프레임 자동 닫힘.
function EvalProjectFormModalContainer({ data, type }) {
  const { workspaceId, project } = data;
  const isEdit = type === 'EDIT_EVAL_PROJECT';

  const [name, setName] = useState(project?.name ?? '');
  const [evalType, setEvalType] = useState(project?.eval_type ?? 'reference');
  const [description, setDescription] = useState(project?.description ?? '');

  // 프레임이 submit 버튼 로딩/비활성을 관리하므로 creating 플래그 불필요.
  // 수정 모드는 이름을 잠그므로 이름 검증이 게이트가 될 수 없다(항상 통과).
  const validate = isEdit || !!name.trim();

  // 프레임 계약: truthy 반환 시 closeModal(type) 자동, falsy 시 재활성.
  const onSubmit = async () => {
    // workspace_id 는 라우트 파라미터에서 온다 — 모델을 더 이상 받지 않으므로 BE 가
    // model_id 로 도출하던 종전 경로(설계 계약)가 성립하지 않는다.
    const res = isEdit
      ? await updateEvalProject(project.id, { description })
      : await createEvalProject({
          name: name.trim(),
          eval_type: evalType,
          description,
          workspace_id: Number(workspaceId),
        });
    if (res.status !== STATUS_SUCCESS) {
      errorToastMessage(res.error, res.message);
      return false;
    }
    data.submit?.func?.(res.result);
    return true;
  };

  return (
    <EvalProjectFormModal
      type={type}
      data={data}
      validate={validate}
      name={name}
      setName={setName}
      evalType={evalType}
      setEvalType={setEvalType}
      description={description}
      setDescription={setDescription}
      onSubmit={onSubmit}
    />
  );
}

export default EvalProjectFormModalContainer;
