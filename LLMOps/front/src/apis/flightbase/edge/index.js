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

// 배포된 컨테이너 중지 — remoteManager /ops op:"stop". 디바이스 쪽 stop 은 원래
// 구현돼 있었고 플랫폼 호출 경로만 없어서, 배포는 되지만 중지가 불가능했다.
// remote_manager_url 이 없는 heartbeat-only 디바이스는 BE 가 사유를 구분해 거절한다.
export const stopEdgeWorker = async (workerId) => {
  return await callApi({
    url: `edge/workers/${workerId}/stop`,
    method: 'post',
  });
};

// SP-6 / 3.10 — 양자화 패키지(GGUF)를 Edge 워커에 remoteManager /ops 로 배포.
export const deployEdgeWorker = async (workerId, body) => {
  // body: { image, model_name?, model_version?, gguf_path?, lineage_id?, params? }
  // lineage_id 가 있으면 BE 가 아티팩트 다운로드 URL(model_url)을 발급해 디바이스가
  // 모델 파일을 직접 받아간다(계약 v1). 없으면 종전대로 문자열만 전달.
  return await callApi({
    url: `edge/workers/${workerId}/deploy`,
    method: 'post',
    body,
  });
};

// ops 토큰 — 플랫폼이 디바이스의 /ops·/metrics 를 부를 때 제시하는 공유 키(admin).
// 디바이스별 토큰과 달리 **조회를 허용**한다. 전 디바이스 공통 값이라 1회 표시 방식이면
// 디바이스를 한 대 추가할 때마다 전체를 재발급해야 한다.
export const getEdgeOpsToken = async () => {
  return await callApi({ url: 'edge/ops-token', method: 'get' });
};

// 재발급 — 기존 키는 prev 로 내려가 아직 교체되지 않은 디바이스가 계속 동작한다(무중단).
export const rotateEdgeOpsToken = async () => {
  return await callApi({ url: 'edge/ops-token/rotate', method: 'post' });
};

// 옛 키 폐기 — 이 시점부터 교체하지 않은 디바이스는 401 이 된다.
export const retireEdgeOpsTokenPrev = async () => {
  return await callApi({ url: 'edge/ops-token/retire-prev', method: 'post' });
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
