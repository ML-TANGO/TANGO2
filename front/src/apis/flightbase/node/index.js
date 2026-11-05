import { callApi } from '@src/network';

// 플랫폼 GPU 풀 현황 — { total, in_use, reserved, free, nodes }.
//   fb_resource 가 자원 read-model 의 정본이다(관리자 노드 화면도 같은 앱의 nodes/node-info
//   를 쓴다). node-info 와 나눠 둔 이유는 **세는 술어가 다르기 때문**이다: node-info 의
//   used 는 모니터링이 채우는 used_info 만 보는데, external 컨테이너 잡은 GPU 를 예약
//   키(SETNX)로 잡고 그건 used_info 를 건드리지 않는다. 그 차이를 무시하면 화면은
//   "가용 3장" 이라 말하고 실행은 실패한다.
//   ⚠️ 보장이 아니라 사전 안내다 — 조회와 실행 사이에 다른 잡이 GPU 를 가져갈 수 있고
//   (TOCTOU), 최종 판정은 스케줄러의 원자적 claim 이다.
//   workspace_id 를 주면 `workspace {hard, used, free}` 가 함께 온다 — 사용자가 '내 몫' 으로
//   이해하는 축이고 화면에 세울 숫자다. 다만 **실행을 막는 축은 아니다**: external 경로는
//   워크스페이스 쿼터를 읽지 않고 차트도 nvidia.com/gpu 를 요청하지 않아 K8s ResourceQuota
//   의 GPU 항목이 증가하지 않는다. 실제 게이트는 클러스터 풀이라, 화면은 workspace 로 말하고
//   차단은 둘 중 빡빡한 쪽을 따른다.
export const getGpuAvailability = async (workspace_id) => {
  return await callApi({
    url: 'nodes/gpu-availability',
    method: 'get',
    params: workspace_id ? { workspace_id } : {},
  });
};
