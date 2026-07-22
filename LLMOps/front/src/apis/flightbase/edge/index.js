import { callApi } from '@src/network';

// SP-8 / 수용계획서 3.1 — Edge 워커 노드 + 커스텀 레이블 (admin).

export const getEdgeWorkers = async () => {
  return await callApi({ url: 'edge/workers', method: 'get' });
};

export const registerEdgeWorker = async (body) => {
  // body: { name, device_type?, remote_manager_url? }
  // device_id 는 서버가 자동 생성(응답 result.device_id). name 은 필수·중복 불가.
  return await callApi({ url: 'edge/workers', method: 'post', body });
};

export const refreshEdgeWorker = async (workerId) => {
  // remoteManager /metrics 폴링 → 연결상태/자원/배포 갱신.
  return await callApi({
    url: `edge/workers/${workerId}/refresh`,
    method: 'post',
  });
};

// SP-8 P1 — 노드별 Bearer 토큰 발급/rotation. 평문 토큰은 응답에서 1회만 노출.
export const issueEdgeToken = async (workerId) => {
  return await callApi({
    url: `edge/workers/${workerId}/token`,
    method: 'post',
  });
};

export const deleteEdgeWorker = async (workerId) => {
  return await callApi({ url: `edge/workers/${workerId}`, method: 'delete' });
};

// SP-6 / 3.10 — 양자화 패키지(GGUF)를 Edge 워커에 remoteManager /ops 로 배포.
export const deployEdgeWorker = async (workerId, body) => {
  // body: { image, model_name?, model_version?, gguf_path?, params? }
  return await callApi({
    url: `edge/workers/${workerId}/deploy`,
    method: 'post',
    body,
  });
};

// SP-8 P4b — 커스텀 레이블 조회(노드 + 엣지워커 공용). target_type/target_id 없이 호출
// 하면 전체. K8s 노드 레이블은 target_type='node', target_id=hostname 으로 저장/조회.
export const getEdgeLabels = async (targetType, targetId) => {
  const params = [];
  if (targetType) params.push(`target_type=${encodeURIComponent(targetType)}`);
  if (targetId) params.push(`target_id=${encodeURIComponent(targetId)}`);
  const query = params.length ? `?${params.join('&')}` : '';
  return await callApi({ url: `edge/labels${query}`, method: 'get' });
};

export const upsertEdgeLabel = async (body) => {
  // body: { target_type, target_id, label_key, label_value? }
  return await callApi({ url: 'edge/labels', method: 'post', body });
};

export const deleteEdgeLabel = async (labelId) => {
  return await callApi({ url: `edge/labels/${labelId}`, method: 'delete' });
};
