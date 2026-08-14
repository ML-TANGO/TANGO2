import { callApi } from '@src/network';

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
