import { callApi, downloadBlob } from '@src/network';

// ─────────────────────────────────────────────────────────────
// Deployment(배포, D6) API 래퍼
// BE = apps/fb_deployment (FastAPI, prefix `/deployments`).
// 응답 규약: callApi 가 BE `{status:1, result}` → `{status:STATUS_SUCCESS, result}` 로 정규화.
// 호출부는 res.status === STATUS_SUCCESS 확인 후 res.result 사용.
// ─────────────────────────────────────────────────────────────

// ── 핵심 CRUD ────────────────────────────────────────────────

// 워크스페이스 배포 목록 (첫 화면). 폴링 대상.
export const getDeployments = async (workspaceId) => {
  return await callApi({
    url: `deployments?workspace_id=${workspaceId}`,
    method: 'get',
  });
};

// 단일 배포 GET (수정용 정보).
export const getDeployment = async (deploymentId) => {
  return await callApi({
    url: `deployments/${deploymentId}`,
    method: 'get',
  });
};

// 배포 상세 정보 (사이드탭 - 배포정보).
export const getDeploymentDetail = async (deploymentId) => {
  return await callApi({
    url: `deployments/detail/${deploymentId}`,
    method: 'get',
  });
};

// 배포 생성 (목록에서 단일 생성). body = CreateModel.
export const createDeployment = async (body) => {
  return await callApi({
    url: 'deployments',
    method: 'post',
    body,
  });
};

// 배포 수정 (단일). body = UpdateModel.
export const updateDeployment = async (body) => {
  return await callApi({
    url: 'deployments',
    method: 'put',
    body,
  });
};

// 배포 삭제 (user 단일 / admin 복수). idList = 단일 id 또는 id 배열.
export const deleteDeployments = async (idList) => {
  const ids = Array.isArray(idList) ? idList.join(',') : idList;
  return await callApi({
    url: `deployments/${ids}`,
    method: 'delete',
  });
};

// 배포 중지.
export const stopDeployment = async (deploymentId) => {
  return await callApi({
    url: `deployments/stop?deployment_id=${deploymentId}`,
    method: 'get',
  });
};

// 즐겨찾기 등록 / 해제.
export const bookmarkDeployment = async (deploymentId) => {
  return await callApi({
    url: 'deployments/bookmark',
    method: 'post',
    body: { deployment_id: deploymentId },
  });
};

export const unbookmarkDeployment = async (deploymentId) => {
  return await callApi({
    url: 'deployments/bookmark',
    method: 'delete',
    body: { deployment_id: deploymentId },
  });
};

// ── 클러스터 API 게시 (D6 신규 — Kong key-auth 레이어) ──────────
// BE: apps/fb_deployment service.publish/get/rotate/unpublish_deployment_api.
// 키 원본은 Kong 보관(미저장), 표시 시 Kong fetch. 소유자만 호출 가능(능동 소유권 체크).

// 게시: 엔드포인트+키 발급 (key-auth plugin 부착 + consumer/key 생성).
// result: { endpoint, consumer, api_key, published_at }
export const publishDeploymentApi = async (deploymentId) => {
  return await callApi({
    url: `deployments/${deploymentId}/api-publish`,
    method: 'post',
  });
};

// 게시 정보 조회 (키 = Kong fetch). 미게시면 status=0.
export const getDeploymentApi = async (deploymentId) => {
  return await callApi({
    url: `deployments/${deploymentId}/api-publish`,
    method: 'get',
  });
};

// 키 회전 (기존 키 폐기 후 재발급, create-first → 0-key 윈도우 없음).
// result: { api_key }
export const rotateDeploymentApiKey = async (deploymentId) => {
  return await callApi({
    url: `deployments/${deploymentId}/api-publish/rotate-key`,
    method: 'post',
  });
};

// 게시 해제 (plugin 제거 + consumer/key 삭제, 멱등).
export const unpublishDeploymentApi = async (deploymentId) => {
  return await callApi({
    url: `deployments/${deploymentId}/api-publish`,
    method: 'delete',
  });
};

// ── 접근 로그 (기존 fb_deployment 재사용) ──────────────────────

// 접근 로그 파일 다운로드 (nginx / api 로그). blob 반환.
export const downloadApiLog = async ({
  deploymentId,
  nginxLog = false,
  apiLog = true,
  workerList,
  startTime,
  endTime,
}) => {
  const params = new URLSearchParams();
  params.append('deployment_id', deploymentId);
  params.append('nginx_log', nginxLog);
  params.append('api_log', apiLog);
  if (workerList) params.append('worker_list', workerList);
  if (startTime) params.append('start_time', startTime);
  if (endTime) params.append('end_time', endTime);
  return await downloadBlob({
    url: `deployments/download_api_log?${params.toString()}`,
  });
};

// 접근 로그 삭제.
export const deleteApiLog = async ({ deploymentId, endTime, workerList }) => {
  const params = new URLSearchParams();
  params.append('deployment_id', deploymentId);
  if (endTime) params.append('end_time', endTime);
  if (workerList) params.append('worker_list', workerList);
  return await callApi({
    url: `deployments/api_log?${params.toString()}`,
    method: 'delete',
  });
};
