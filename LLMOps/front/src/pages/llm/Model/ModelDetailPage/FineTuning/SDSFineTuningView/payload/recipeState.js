// SDS external(recipe) 학습의 **파생 상태** — 순수 모듈.
//
// 완료 phase 는 세션 state 가 아니라 **커밋에서 derive** 한다(reload 생존).
// 커밋명 규약 = `{phase.id}-{YYYYMMDD}-{HHMMSS}` (llm_model service.py).
//
// ⚠️ 순수성 불변식: React / 네트워크 / `@src` alias / 어떤 import 도 금지
// (plain node 차분 검증의 전제). recipeParams.js 와도 서로 import 하지 않는다.

/** 정규식 메타문자 이스케이프 — phase.id 를 anchored 패턴에 끼울 때 사용. */
export const escapeRegExp = (s) =>
  String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * phase.id → 최신 커밋 이름.
 *
 * ⚠️ `startsWith(`${id}-`)` 를 쓰면 `lora` 가 `lora-cc3m-...` 를 오매칭한다
 * (phase.id 가 하이픈을 허용). 그래서 타임스탬프까지 **anchored 정규식**으로
 * 정확 매칭한다. ts 가 고정폭이라 lexicographic 정렬 = 시간순.
 */
export const derivePhaseCommitMap = (commits, phases) => {
  const map = {};
  (phases || []).forEach((p) => {
    const re = new RegExp(`^${escapeRegExp(p.id)}-\\d{8}-\\d{6}$`);
    const matched = (commits || [])
      .map((c) => c && c.name)
      .filter((n) => typeof n === 'string' && re.test(n))
      .sort();
    if (matched.length) map[p.id] = matched[matched.length - 1];
  });
  return map;
};

/**
 * phase 카드에 표시할 상태.
 * 활성(실행 중) phase 는 라이브 SSE 상태를, 그 외 커밋이 있으면 done, 나머지 idle.
 */
export const derivePhaseStatus = (
  phase,
  activePhaseId,
  activePhaseStatus,
  donePhases,
) => {
  if (phase.id === activePhaseId && activePhaseStatus) return activePhaseStatus;
  if ((donePhases || new Set()).has(phase.id)) return 'done';
  return 'idle';
};

/**
 * 실행 가능 게이트 — (a) 활성 job 없음(한 번에 한 job) + (b) chain_from 선행 완료.
 * 학습 대상(freeze)은 phase 가 결정하므로 별도 토글 게이트는 없다.
 */
export const canRunPhase = (phase, { anyRunning, donePhases } = {}) => {
  if (!phase) return false;
  if (anyRunning) return false;
  const done = donePhases || new Set();
  if (phase.chain_from && !done.has(phase.chain_from)) return false;
  return true;
};
