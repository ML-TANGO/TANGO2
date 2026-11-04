import { API_HOST, callApi } from '@src/network';

// llm_data_pipeline 서비스 — Kong ingress /api/(data-pipelines).
// 학습 데이터 구축 파이프라인(업로드 → 전처리 → 필터 → 생성 → VLM 심사 → 검수 →
// 분포 분석 → 구성·분할 → 버전 릴리스).
//
// 화면은 아직 mock/ 데이터를 쓰고 있고, 여기가 실제 연결 지점이다. 화면 컴포넌트는
// props 로만 받으므로 mock import 를 이 모듈 호출로 바꾸면 된다.

// ── 공용 상수 ───────────────────────────────────────────────────────────────
// 4축·임계값·유형·기능 라이브러리를 서버가 정본으로 내려준다. FE 가 같은 값을
// 하드코딩하면 서버에서 기준을 바꿔도 화면이 옛 값을 계속 보여준다.
export const getPipelineMeta = async () =>
  callApi({ url: 'data-pipelines/meta', method: 'get' });

// ── 소스(원본이 들어 있는 기존 데이터셋) ────────────────────────────────────
// 경로 규칙("{access}/{이름}{서브폴더}")과 작업 데이터셋 제외를 서버가 처리한다.
// FE 가 경로를 조립하면 규칙이 두 곳으로 갈라져, 한쪽만 고치면 노드가 조용히
// /datasets 전체를 훑는다. 응답의 `path` 를 그대로 sources 에 넣으면 된다.
export const listSourceDatasets = async (workspaceId) =>
  callApi({
    url: 'data-pipelines/source-datasets',
    method: 'get',
    params: { workspace_id: workspaceId },
  });

export const listSourceFolders = async (datasetId, workspaceId) =>
  callApi({
    url: `data-pipelines/source-datasets/${datasetId}/folders`,
    method: 'get',
    params: { workspace_id: workspaceId },
  });

// ── 데이터셋 ────────────────────────────────────────────────────────────────
export const listDatasets = async (workspaceId) =>
  callApi({ url: 'data-pipelines/datasets', method: 'get', params: { workspace_id: workspaceId } });

// body: { workspace_id, name, description?, preset: 'generic'|'sds_colreg' }
export const createDataset = async (body) =>
  callApi({ url: 'data-pipelines/datasets', method: 'post', body });

export const getDataset = async (datasetId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}`, method: 'get' });

// body: { name?, description?, state? }
export const updateDataset = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}`, method: 'put', body });

export const deleteDataset = async (datasetId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}`, method: 'delete' });

// ── 업로드 ──────────────────────────────────────────────────────────────────
// → { summary: {total, registered, duplicate, failed}, failures: [{reason, count, paths}], assets: [...] }
export const getAssets = async (datasetId, params = {}) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/assets`, method: 'get', params });

// 드라이브에서 고른 원본을 이 파이프라인에 등록한다(파일 업로드가 아니라 참조 등록).
// body: { assets: [{ name, path, kind, size_bytes, status }] }
export const registerAssets = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/assets`, method: 'post', body });

// ── 파이프라인 노드 ─────────────────────────────────────────────────────────
// 노드마다 input_type/output_type 과 경고(좌표 깨짐·재심사 필요)가 함께 온다.
export const getFlow = async (datasetId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/flow`, method: 'get' });

// 전체 교체. 해양 COLREG 프리셋은 구성 고정이라 서버가 거부한다.
// body: { preset, nodes: [{kind, name, steps, config}], flow: [[a,b], ...] }
export const replaceFlow = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/flow`, method: 'put', body });

// ── 실행 이력 · 산출물 ──────────────────────────────────────────────────────
// 노드 잡은 비동기다. 실행 직후에는 running 으로 보이고, BE 리콘사일러(20초 주기)가
// 산출물을 확인해야 done/failed 로 바뀐다 — 화면은 폴링으로 따라가야 한다.
// params: { node_index?, limit? }. 목록 응답에는 funnel 전문이 빠져 있다(응답 비대 방지).
export const listRuns = async (datasetId, params = {}) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/runs`, method: 'get', params });

// 단건 + funnel 전문(단계별 in/out/dropped).
export const getRun = async (datasetId, runId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/runs/${runId}`, method: 'get' });

// params: { kind: 'passed'|'dropped', limit, offset }
// 'passed' 는 source_file 과 항목별 has_thumb 을, 'dropped' 는 reasons{사유:건수}를 함께 준다.
//
// '입력' 열 전용 엔드포인트는 일부러 두지 않았다 — 입력은 곧 상류 실행의 통과분이므로
// 화면이 이 함수를 상류 run_id 로 한 번 더 부른다. 그래야 노드가 늘어도 API 가 안 는다.
export const previewRun = async (datasetId, runId, params = {}) =>
  callApi({
    url: `data-pipelines/datasets/${datasetId}/runs/${runId}/preview`,
    method: 'get',
    params,
  });

// 썸네일은 JSON 이 아니라 image/jpeg 바이트다 — <img src> 에 직접 건다.
// 노드는 앞부분 일부만 썸네일로 만들므로(전량이면 용량이 터진다) preview 의
// has_thumb 이 false 인 항목에 걸면 깨진 이미지가 뜬다. 반드시 걸러서 부른다.
export const runThumbUrl = (datasetId, runId, assetId) =>
  `${API_HOST}data-pipelines/datasets/${datasetId}/runs/${runId}/thumb/${assetId}`;

// 레코드의 원본 이미지. 썸네일(runThumbUrl)과 다른 경로인 이유: 썸네일은 실행마다
// 앞부분 일부만 만들어지는데(100건 중 24건) 검수 큐는 점수 낮은 순이라 정작 열어 볼
// 레코드가 표본에 없다. 그리고 레코드의 asset_ref 는 슬래시를 포함한 경로여서 단일
// 세그먼트만 받는 썸네일 경로에 넣을 수 없다. 서버가 레코드 id 로 해결한다.
export const recordImageUrl = (datasetId, recordId) =>
  `${API_HOST}data-pipelines/datasets/${datasetId}/records/${recordId}/image`;

// 설정 차이 · 단계별 funnel 차이 · 카운트 증감.
// 같은 노드의 실행끼리만 비교된다 — 다른 노드면 서버가 거부한다.
export const compareRuns = async (datasetId, a, b) =>
  callApi({
    url: `data-pipelines/datasets/${datasetId}/runs/compare`,
    method: 'get',
    params: { a, b },
  });

// body: { dry_run, sample_size }
// dry_run 이면 표본만 돌려 `_preview/` 에 남기고 이력에 안 남긴다 — 사용자가 기능을
// 껐다 켜며 결과를 비교하는 경로다. 전량 실행은 `_runs/{run_id}/` 로 간다.
export const runStage = async (datasetId, stage, body) =>
  callApi({
    url: `data-pipelines/datasets/${datasetId}/stages/${stage}/run`,
    method: 'post',
    body,
  });

// ── 단계 설정 ───────────────────────────────────────────────────────────────
// stage: preprocess | filter | generate | gate
export const getStage = async (datasetId, stage) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/stages/${stage}`, method: 'get' });

// body: { enabled: {기능명: bool}, params: {...} }
export const saveStageConfig = async (datasetId, stage, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/stages/${stage}`, method: 'put', body });

// body: { generator_model, judge_model, templates, prompt, per_image, answer_length,
//         language, hard_negative_pct }
// 생성 모델과 심사 모델이 같으면 서버가 거부한다(자가심사 차단).
export const saveGenerateConfig = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/stages/generate`, method: 'put', body });

// body: { thresholds: {align, imgdep, answer, unique}, max_regenerate }
export const saveGateConfig = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/stages/gate`, method: 'put', body });

// → { pass_rate, pass_rate_flag, fail_distribution, top_fail_axis }
export const getGateSummary = async (datasetId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/gate-summary`, method: 'get' });

// ── 검수 ────────────────────────────────────────────────────────────────────
// params: { order: 'score_asc'|'random'|'taxonomy', taxonomy?, review_state?, limit, offset }
export const listRecords = async (datasetId, params = {}) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/records`, method: 'get', params });

// 화면 URL 이 vdf-0009855 같은 사람이 읽는 키를 쓰므로 그 경로로 연다.
export const getRecordByKey = async (datasetId, recordKey) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/records/${recordKey}`, method: 'get' });

export const getRecord = async (recordId) =>
  callApi({ url: `data-pipelines/records/${recordId}`, method: 'get' });

// body: { verdict: 'approved'|'edited'|'rejected', taxonomy?, edited_question?, edited_answer? }
// 'edited' 는 수정본이, 'rejected' 는 오류 유형이 반드시 있어야 한다.
export const reviewRecord = async (recordId, body) =>
  callApi({ url: `data-pipelines/records/${recordId}/review`, method: 'post', body });

// ── 분포 분석 ───────────────────────────────────────────────────────────────
// 유형마다 record_count 와 asset_count 를 함께 준다 — 업로드 문제인지 생성 문제인지 가른다.
export const getCoverage = async (datasetId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/coverage`, method: 'get' });

// ── 구성 · 버전 ─────────────────────────────────────────────────────────────
// body: { formats: ['Qwen3-VL', 'Gemma 3', 'HuggingFace messages'] }
export const verifyTrainFormat = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/verify-format`, method: 'post', body });

export const listVersions = async (datasetId) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/versions`, method: 'get' });

// body: { version, mix, split, split_by }
export const createVersion = async (datasetId, body) =>
  callApi({ url: `data-pipelines/datasets/${datasetId}/versions`, method: 'post', body });
