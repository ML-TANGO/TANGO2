// 노드 종류(kind) ↔ 단계 이름(stage) 매핑.
//
// 파이프라인 캔버스와 단계 설정 화면이 같은 판정을 해야 한다 — 한쪽만 고치면 캔버스에서
// 연 노드와 설정 화면이 서로 다른 노드를 가리키게 된다. BE `STAGE_NODE_KINDS` 의 역방향.

// kind='src' 는 해양 프리셋에서 영상·AIS 둘 다라 여기 두지 않고 stageOfNode 가 가른다.
export const STAGE_BY_KIND = {
  prep: 'preprocess',
  filter: 'filter',
  synth: 'generate',
  gen: 'generate',
  gate: 'gate',
  join: 'sds_join',
  calc: 'sds_colreg',
};

// 실행을 붙이지 않은 종류. 데이터 노드는 마운트 선택이지 잡이 아니고,
// 조립(out)은 입력 계약이 생성·심사와 함께 정해질 때까지 보류다.
export const NOT_RUNNABLE = new Set(['data', 'out']);

/**
 * 이 노드를 실행할 단계 이름. 없으면 실행할 수 없는 노드다.
 *
 * 해양 프리셋의 원천 노드는 둘 다 kind='src' 다. BE 도 같은 문제를 이름 우선 · 순번
 * 보조로 푼다(STAGE_NODE_PICK) — 이름만 보면 사용자가 개명한 순간 단계가 죽고,
 * 순번만 보면 재배열했을 때 조용히 엉뚱한 노드를 문다. 같은 규칙을 따른다.
 */
export function stageOfNode(node, nodes) {
  if (!node || NOT_RUNNABLE.has(node.kind)) return null;
  return configStageOfNode(node, nodes);
}

/**
 * 이 노드의 **설정을 저장할** 단계. 실행 여부와 무관하다.
 *
 * 데이터 노드는 실행되지 않지만 소스(마운트)를 저장해야 한다 — 실행용 stageOfNode 로
 * 저장 대상을 고르면 데이터 노드의 선택이 갈 곳이 없어 그대로 사라진다.
 *
 * BE 가 노드마다 `stage` 를 실어 준다(같은 `_find_stage_node` 로 계산한 값). 그것이
 * 정본이고, 아래 로컬 규칙은 그 필드가 없는 옛 응답을 위한 보조다 — 두 곳이 갈리면
 * 캔버스에서 연 노드와 저장되는 노드가 달라진다.
 */
export function configStageOfNode(node, nodes) {
  if (!node) return null;
  if (node.stage) return node.stage;
  if (node.kind === 'data') return 'data';
  if (node.kind !== 'src') return STAGE_BY_KIND[node.kind] || null;
  if (node.name === '항해 영상') return 'sds_video';
  if (node.name === 'AIS 로그') return 'sds_ais';
  const srcs = (nodes || []).filter((n) => n.kind === 'src');
  return srcs.indexOf(node) === 0 ? 'sds_video' : 'sds_ais';
}

/** 이 단계를 담당하는 노드와 그 위치. 설정 화면이 실행 결과를 찾을 때 쓴다. */
export function findStageNode(nodes, stage) {
  const idx = (nodes || []).findIndex((n, _i, arr) => stageOfNode(n, arr) === stage);
  return idx < 0 ? { node: null, index: -1 } : { node: nodes[idx], index: idx };
}

/**
 * 노드의 상류 실행 — 설정 화면·드로어의 '입력' 열이 이걸로 채워진다.
 * 간선이 없으면 선형 체인으로 본다(BE 가 flow 를 비워 보내면 화면도 선형으로 그린다).
 */
export function upstreamRunOf(nodes, edges, index) {
  if (index < 0) return null;
  const edge = (edges || []).find(([, b]) => b === index);
  const from = edge ? edge[0] : index - 1;
  return nodes?.[from]?.latest_run || null;
}
