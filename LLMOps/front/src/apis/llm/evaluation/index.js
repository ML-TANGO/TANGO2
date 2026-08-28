import { callApi, downloadBlob } from '@src/network';

// llm_evaluation 서비스 (P1b) — Kong ingress /api/(evaluations).
// 벤치마크 평가 런 생성/폴링/이력/상태. (LLM-judge=P2, 전문가=P3.)

// ── 평가 프로젝트 (P2) ────────────────────────────────────────────────
// 프로젝트 = 평가유형 + 이름을 묶는 관리 단위. **모델·데이터셋은 프로젝트가 아니라 런이
// 고른다**(실행 시점 선택) — 한 프로젝트 안에서 모델·데이터셋을 바꿔 가며 견주는 것이
// 프로젝트의 목적이라 생성 시점에 잠글 수 없다. 옛 프로젝트는 project.model_id /
// dataset_ids 를 그대로 갖고 있고(표시용), 새 프로젝트는 null/빈 값이다.

// 프로젝트 생성(대기 상태, run 0개). body: { name, eval_type: 'reference'|'judge'|'expert',
//   description?, workspace_id } — workspace_id 는 라우트 파라미터에서 온다(모델을 안 받으므로
//   서버가 model_id 로 도출할 수 없다). description 은 선택·최대 5000자(VARCHAR(5000) nullable)
//   이며 목록/단건 조회 양쪽 응답에 그대로 실려 온다(카드용 별도 조회 불필요).
//   → get_project shape 반환 { project, runs }.
export const createEvalProject = async (body) => {
  return await callApi({ url: 'evaluations/projects', method: 'post', body });
};

// 워크스페이스 프로젝트 목록(최신순). 프로젝트 update_datetime 은 최근 run 생성 시각이며
// run 이 없으면 프로젝트 create_datetime 과 같다. → { workspace_id, projects: [...] }.
export const listEvalProjects = async (workspaceId) => {
  return await callApi({
    url: 'evaluations/projects',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// 프로젝트 단건(+자식 run 요약). → { project: {...}, runs: { metric_keys, best, runs } }.
export const getEvalProject = async (projectId) => {
  return await callApi({
    url: `evaluations/projects/${projectId}`,
    method: 'get',
  });
};

// 프로젝트 설명 수정 — **확정 계약**(BE 마이그레이션 004, dev 라이브 검증 완료).
//   PUT evaluations/projects/{id}  body { description: string|null }
//   → result { project_id, updated, description }.
//   PATCH 가 아니라 PUT 인 이유: 이 모노레포에 PATCH 라우트가 0개이고, 정확한 유사물인
//   playgrounds.put('/description') 이 PUT 이다. (network.js 의 demo 계정 쓰기 차단도
//   put/post/delete 만 막으므로 PATCH 였다면 demo 가 이 경로로만 쓰기를 통과했을 것이다.)
//   ⚠️ 응답은 **프로젝트 전체가 아니라 작은 dict** 다. 의도된 설계로, get_project 는 running
//   런을 컨테이너와 리콘사일하는 부수효과가 있어 설명 한 줄 저장이 그 왕복을 기다리고 런
//   상태까지 바꾼다. 그래서 저장 후 화면 갱신은 이 응답의 description 을 쓰거나 목록을
//   다시 부른다 — 저장 응답으로 프로젝트를 통째로 갈아끼우지 마라.
//   공백만 보내면 서버가 NULL 로 접는다(빈 설명 = 카드가 no.desc 플레이스홀더를 그림).
//   요청 서술은 여기 한 곳에만 둔다 — 호출부는 updateEvalProject 시그니처만 안다.
const EVAL_PROJECT_UPDATE = (projectId) => ({
  url: `evaluations/projects/${projectId}`,
  method: 'put',
});

export const updateEvalProject = async (projectId, body) => {
  return await callApi({ ...EVAL_PROJECT_UPDATE(projectId), body });
};

// 프로젝트 삭제(FK CASCADE 로 run·채점·이력 자식행 정리). → { project_id, deleted }.
export const deleteEvalProject = async (projectId) => {
  return await callApi({
    url: `evaluations/projects/${projectId}`,
    method: 'delete',
  });
};

// 프로젝트 내 run 비교(same model+dataset=apples-to-apples). → { project_id, metric_keys, best, runs }.
export const compareProjectRuns = async (projectId) => {
  return await callApi({
    url: `evaluations/projects/${projectId}/compare`,
    method: 'get',
  });
};

// ── run 생성 (P2+: 런이 대상을 지정) ──────────────────────────────────
// 전 런 계약 공통 필수: model_id(이 런이 평가할 모델), dataset_ids(정확히 1개).
// 벤치마크 런 생성. body: { project_id, model_id, dataset_ids: [id],
//   benchmarks?: [{ benchmark, metric }] } — 벤치마크→메트릭 매핑(생략 시 전체·권장 메트릭).
// LogicKor 내장 심판(컨테이너가 GPU 에 직접 올리는 심판) 후보 목록.
//   → { models: [{id,label,hf_id,size_gb}], default }.
//   ⚠️ **지금 이걸 부르는 화면은 없다** — 심판은 떠 있는 배포로 일원화했고(judge_playground_id)
//   내장 심판 경로는 BE 에 남겨 둔 채 화면에서만 감췄다(JudgeRunConfig 머리 주석).
//   그 경로를 화면에 되살릴 때 후보를 프론트에 복제하지 말고 이 응답을 그대로 렌더하라 —
//   서버 화이트리스트와 드리프트하면 캐시에 없는 심판이 화면에 떠서
//   "GPU 잡고 몇 분 뒤 실패"가 되살아난다.
export const getBenchmarkJudgeModels = async () => {
  return await callApi({ url: 'evaluations/benchmark/judge-models', method: 'get' });
};

export const runBenchmark = async (body) => {
  return await callApi({ url: 'evaluations/benchmark', method: 'post', body });
};

// 평가 추론 러너(generate) 런 생성 래퍼(runEvalInference)는 지웠다 — 평가 실행이 이미
//   "출력을 만들 배포"를 고르므로 출력을 미리 만들어 두는 별도의 생성 런이 의미를 잃었고,
//   프로젝트 상세에서 그 진입점을 없애며 호출자가 0 이 됐다.
//   ⚠️ BE `POST /evaluations/inference` 는 그대로 살아 있고 **도달만 불가**하다. 되살릴
//   때는 이 자리에 래퍼를 다시 만들면 된다(ProjectDetail.jsx 의 같은 취지 주석 참조).

// 단건 평가 결과 폴링 (ready=true 시 metrics + eval_result lazy 마감).
export const getEvalResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/result`,
    method: 'get',
  });
};

// 교차모델 비교(④ 경량 뷰) — 여러 모델 이력 합쳐 전역 best-per-metric. modelIds: number[].
export const getEvalCompare = async (modelIds) => {
  return await callApi({
    url: 'evaluations/compare',
    method: 'get',
    params: { model_ids: (modelIds || []).join(',') },
  });
};

// 런 단위 교차 비교 후보(P1) — 워크스페이스 전 평가 런(프로젝트 가로지름). 각 항목에
//   project_name/model_name/checkpoint/source_* /metric_set/status/metrics 가 실려 있어
//   화면이 "어느 모델의 어느 체크포인트를 언제 돌린 런인가" 를 날짜 없이도 구분할 수 있다.
export const listEvalRuns = async (workspaceId) => {
  return await callApi({
    url: 'evaluations/runs',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// 런 단위 비교(P1) — 지목한 런들만 열로 세운다. → { runs, metric_keys, best, datasets,
//   dataset_consistent }. dataset_consistent=false 면 서로 다른 데이터셋을 섞어 본 것이라
//   화면이 경고를 띄운다(차단은 하지 않는다).
export const getEvalCompareRuns = async (workspaceId, runIds) => {
  return await callApi({
    url: 'evaluations/compare-runs',
    method: 'get',
    params: {
      workspace_id: workspaceId,
      run_ids: (runIds || []).join(','),
    },
  });
};

// 평가 실패/취소 마킹 (cancelled 면 BE 가 컨테이너도 취소).
export const markEvalStatus = async (modelId, jobId, status) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/status`,
    method: 'post',
    body: { status },
  });
};

// 평가 런 1건 삭제(이력 관리). expert 세션이면 BE 가 FK CASCADE 로 채점/이력 자식행도 정리.
export const deleteEvalRun = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}`,
    method: 'delete',
  });
};

// 벤치마크 대상 워크스페이스 데이터셋 목록 (fb_option, get_dataset_model 과 동일 소스).
export const getEvalDatasets = async (workspaceId) => {
  return await callApi({
    url: 'options/preprocessing/dataset',
    method: 'get',
    params: { workspace_id: workspaceId },
  });
};

// ── LLM 심사 (LLM-as-a-Judge) ────────────────────────────────────────
// 전용 엔드포인트는 없다. 심사 벤치마크(LogicKor)는 벤치마크 런이므로 생성은 runBenchmark
//   ({ benchmarks: ['logickor'], inference_playground_id, judge_playground_id, ... }),
//   결과 폴링은 getEvalResult 를 그대로 쓴다. BE 는 프로젝트 유형과 벤치마크 유형이
//   어긋나면 런 생성을 거부한다.
// 폐기(2026-08-27): runJudge(POST /evaluations/judge) · getJudges(GET /evaluations/judges) ·
//   getJudgeResult(GET /{modelId}/{jobId}/judge-result). 자유 샘플 × 기준 4종 채점은 mock
//   이었고, 외부 API 심판(키·엔드포인트 수취)은 평가가 아니라 배포 표면의 문제라 옮긴다.

// ── 전문가 평가 (P3) ──────────────────────────────────────────────────
// 세션 시작 → { job_id, total, expert_prompt, samples: [{ idx, output,
//   image/image_url/image_served, csv_rows(2D)/csv_text }] }. body: { project_id,
//   model_id, dataset_ids: [id], inference_playground_id? } — 대상은 런이 지정한다.
// expert_prompt(고정 지침)·per-sample csv_rows/csv_text 는 startExpert 시 인라인으로 내려온다
// (이미지는 별도 blob 엔드포인트 expert-image/{idx} 유지). input/reference 는 계약엔 있으나 FE 미표시.
export const startExpert = async (body) => {
  return await callApi({ url: 'evaluations/expert', method: 'post', body });
};

// 세션 샘플 + 기존 채점(재개용).
export const getExpertSamples = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-samples`,
    method: 'get',
  });
};

// 채점 제출(1~5 별점 + 코멘트). body: { sample_idx, score, score_json?, comment? }
// → { rated, total, avg_score, distribution, completed, rater_user, rated_at, rate_count }.
// score_json 은 확장 지점(다기준/구조화 피드백/선호도쌍) — 현재 UI 는 단일 score 만 전송.
export const submitExpertRating = async (modelId, jobId, body) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-rating`,
    method: 'post',
    body,
  });
};

// 세션 진행/결과(상태 + 채점 목록 + 채점 이력 + 합격률).
export const getExpertResult = async (modelId, jobId) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-result`,
    method: 'get',
  });
};

// 멀티모달 — 전문가 샘플 이미지(서버 보관 NFS 이미지) blob. jf 헤더 인증 경유라 <img src>
// 직접 GET(헤더 미탑재) 대신 blob 으로 받아 objectURL 로 렌더. URL 이미지는 FE 가 직접 렌더(미사용).
export const fetchExpertImageBlob = async (modelId, jobId, idx) => {
  return await downloadBlob({
    url: `evaluations/${modelId}/${jobId}/expert-image/${idx}`,
  });
};

// 지연 단위 VLM 실추론 — 전문가가 여는 샘플 1개를 바인드된 배포 SDS 모델로 추론해 output 을
// 실출력으로 교체·영속. → { real_output, sample }. 미바인드/비-VLM/이미 실출력/실패는 real_output=false.
export const inferExpertSample = async (modelId, jobId, sampleIdx) => {
  return await callApi({
    url: `evaluations/${modelId}/${jobId}/expert-infer/${sampleIdx}`,
    method: 'post',
  });
};
