import { useEffect, useMemo, useState } from 'react';

import EvalProjectFormModal from '@src/components/Modal/EvalProjectFormModal';

import { createEvalProject, getEvalDatasets } from '@src/apis/llm/evaluation';
import { STATUS_SUCCESS } from '@src/network';

import { errorToastMessage } from '@src/utils';

const MAX_DATASETS = 10; // 다중 비활성(보존): 현재 BE dataset_ids max_length=1(단일 강제). 다중 복원 시 참조.

// 평가 프로젝트 생성 모달 컨테이너(스마트) — Redux 모달 시스템 편입.
//   data(=modalData) = { submit:{text,func}, cancel:{text}, workspaceId }. type = 'CREATE_EVAL_PROJECT'.
//   필드 state·데이터셋 로드·검증·생성(createEvalProject)을 소유하고 프레젠테이셔널에 위임한다.
//   생성 성공 시 data.submit.func(get_project) 로 부모(EvaluationMenu)가 상세로 이동, true 반환 → 프레임 자동 닫힘.
function EvalProjectFormModalContainer({ data, type }) {
  const { workspaceId } = data;

  const [name, setName] = useState('');
  const [evalType, setEvalType] = useState('benchmark');
  const [modelId, setModelId] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [selDatasets, setSelDatasets] = useState([]); // 배열 계약 보존(단일 강제, len 0|1)

  useEffect(() => {
    // 취소 가드(ProjectDetail.jsx 선례): 언마운트/workspaceId 변경 중 늦은 응답이
    // setState 하거나 stale 데이터로 덮어쓰지 않도록 방지.
    let cancelled = false;
    (async () => {
      const res = await getEvalDatasets(workspaceId);
      if (cancelled) return;
      if (res.status === STATUS_SUCCESS) {
        const raw = Array.isArray(res.result)
          ? res.result
          : (res.result?.list ?? []);
        setDatasets(
          raw
            .map((d) => ({
              id: d.id ?? d.dataset_id,
              name: d.name ?? d.dataset_name,
              format: d.format ?? d.data_format ?? null,
            }))
            .filter((d) => d.id != null),
        );
      } else {
        errorToastMessage(res.error, res.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  // Selectbox 검색형 옵션 { label, value } — 포맷은 라벨에 병기.
  const datasetOptions = useMemo(
    () =>
      datasets.map((d) => ({
        label: d.format ? `${d.name} (${d.format})` : d.name,
        value: d.id,
      })),
    [datasets],
  );

  // 단일 강제(2026-07-19): 데이터셋 1개만 선택. BE 도 dataset_ids max_length=1.
  // 다중 복원 대비 selDatasets 배열 계약/MAX_DATASETS 상수는 보존.
  const selectedDataset = useMemo(
    () => datasetOptions.find((o) => o.value === selDatasets[0]) ?? null,
    [datasetOptions, selDatasets],
  );

  const onSelectDataset = (item) => {
    setSelDatasets(item?.value != null ? [item.value] : []);
  };

  // 프레임이 submit 버튼 로딩/비활성을 관리하므로 creating 플래그 불필요.
  const validate =
    !!name.trim() &&
    !!modelId &&
    selDatasets.length > 0 &&
    selDatasets.length <= MAX_DATASETS;

  // 프레임 계약: truthy 반환 시 closeModal(type) 자동, falsy 시 재활성.
  const onSubmit = async () => {
    // workspace_id 는 BE 가 model_id 로 도출(설계 계약 — 바디 미포함).
    const res = await createEvalProject({
      name: name.trim(),
      model_id: Number(modelId),
      dataset_ids: selDatasets,
      eval_type: evalType,
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
      workspaceId={workspaceId}
      validate={validate}
      name={name}
      setName={setName}
      evalType={evalType}
      setEvalType={setEvalType}
      modelId={modelId}
      setModelId={setModelId}
      datasetOptions={datasetOptions}
      selectedDataset={selectedDataset}
      onSelectDataset={onSelectDataset}
      onSubmit={onSubmit}
    />
  );
}

export default EvalProjectFormModalContainer;
