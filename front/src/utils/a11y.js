// 접근성 공용 유틸.

// 카드·칩형 옵션 묶음(WAI-ARIA radiogroup / tablist)의 키보드 조작.
//   방향키로 옮기고(→↓ 다음 / ←↑ 이전, 양끝에서 순환) Home/End 로 양끝.
//   옮긴 값을 곧바로 고르고(onPick) 포커스도 함께 옮긴다 — radiogroup 과 tablist 의
//   자동 활성화(automatic activation) 규약이 같다.
//
// 디자인시스템 Radio 는 라벨 텍스트만 렌더해 카드·칩형 옵션에 쓸 수 없어, 그런 자리는
// 전부 button[role=radio|tab] 을 직접 세운다. 그 자리마다 같은 핸들러를 다시 쓰던 것을
// (평가 표면에서만 3벌) 여기 한 곳으로 모은다.
//
// ⚠️ values 에는 **고를 수 있는 값만** 넘긴다 — 비활성 항목으로 방향키가 넘어가면
//    선택은 되는데 컨트롤은 안 나오는 상태가 만들어진다.
// ⚠️ 각 버튼에 `data-value={값}` 과 roving tabIndex(고른 것만 0, 나머지 -1)를 함께
//    걸어야 완성된다 — 이 함수는 포커스를 그 속성으로 찾는다.
//
// groupRef: 옵션들을 감싼 요소의 ref, values: 고를 수 있는 값 배열,
// current: 현재 값, onPick: 값을 고르는 콜백. → onKeyDown 핸들러.
export const moveRovingFocus = (groupRef, values, current, onPick) => (e) => {
  if (!values.length) return;
  const at = values.indexOf(current);
  let next = null;
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown')
    next = values[(at + 1) % values.length];
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp')
    next = values[(at - 1 + values.length) % values.length];
  else if (e.key === 'Home') next = values[0];
  else if (e.key === 'End') next = values[values.length - 1];
  if (next == null) return;
  e.preventDefault();
  onPick(next);
  groupRef.current?.querySelector(`[data-value="${next}"]`)?.focus();
};
