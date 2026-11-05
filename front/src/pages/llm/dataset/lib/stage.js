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
  // 필드가 **있으면** null 도 정본이다 — BE 는 단계당 노드 하나만 잡으므로 같은 kind 의
  // 두 번째 노드는 null 이 온다. 이걸 kind 로 다시 추정하면 첫 노드의 설정 화면이 열리고
  // 저장 · 실행이 그 노드에 가서 덮는다.
  if ('stage' in node) return node.stage;
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

/**
 * 실행 시각을 비교 가능한 수로.
 *
 * BE 는 DATETIME 을 **드라이버에 따라 datetime 또는 str 로** 내려준다(service.py 의
 * `_age_seconds` 주석이 명시한다). 전자는 'T', 후자는 공백으로 구분되는데 공백(0x20)이
 * 'T'(0x54) 보다 작아, 두 형식이 한 응답에 섞이면 사전식 비교가 조용히 뒤집힌다.
 * 낡은 노드를 최신으로 잘못 판정하면 사용자는 어긋난 데이터를 그대로 릴리스한다.
 */
function runTimeKey(run) {
  const raw = run?.started_at;
  if (!raw) return null;
  const ms = Date.parse(String(raw).replace(' ', 'T'));
  return Number.isNaN(ms) ? null : ms;
}

/**
 * 이 노드의 실행이 상류보다 오래됐는가.
 *
 * 상류를 다시 돌리면 하류 숫자는 **옛 입력의 결과**로 남는다. 화면은 노드마다 숫자를
 * 같은 비중으로 나란히 놓기 때문에, 표시가 없으면 서로 20일 떨어진 실행도 한 번의
 * 일관된 실행처럼 읽힌다(생성 13건 → 심사 100건 입력 같은 모순이 그렇게 숨는다).
 *
 * 상류가 둘인 노드(조인)가 있으므로 간선을 모두 본다 — `upstreamRunOf` 는 하나만
 * 집어 오므로 여기서는 쓰지 않는다.
 *
 * 폴백은 **간선을 아예 못 받았을 때만** 선형(index-1)으로 본다. "이 노드로 들어오는
 * 간선이 없을 때" 로 하면 안 된다 — BE `_derive_edges` 가 원천 노드(kind in data/src)를
 * 건너뛰므로 정상 그래프에서도 소스는 진입 간선이 0개이고, 그러면 무관한 형제 소스와
 * 시각을 비교해 오탐이 난다(해양 프리셋의 'AIS 로그' 가 '항해 영상' 을 상류로 오인).
 *
 * 한계: 판정은 직속 상류 1홉만 본다. 0→1→2 에서 0 만 재실행하면 1 에는 배지가 붙지만
 * 2 에는 붙지 않는다. 다단 전파는 위상 순회가 필요해 별도 과제로 둔다.
 */
export function isStaleRun(nodes, edges, index) {
  const mineAt = runTimeKey(nodes?.[index]?.latest_run);
  if (mineAt === null) return false;

  const all = edges || [];
  const ups = all.filter(([, b]) => b === index).map(([a]) => a);
  const from = ups.length ? ups : (all.length ? [] : [index - 1]);

  return from.some((i) => {
    const up = nodes?.[i]?.latest_run;
    // 미리보기·미완료 실행은 정식 산출물을 바꾸지 않는다(하류 입력은 성공한 비-미리보기
    // 실행만 쓴다). 이걸 세면 상류에서 '미리보기' 를 누르는 것만으로 배지가 붙는다.
    if (!up || up.dry_run || up.status !== 'done') return false;
    const upAt = runTimeKey(up);
    return upAt !== null && upAt > mineAt;
  });
}
