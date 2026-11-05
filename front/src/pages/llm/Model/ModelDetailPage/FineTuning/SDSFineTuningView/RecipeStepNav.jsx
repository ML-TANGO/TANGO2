// SDS 레시피 phase 네비 — 셸의 `fullWidthTop` 슬롯(box 위 full-width).
//
// 왜 하우스에 대응처가 없는가(설계 §2-A #1 / §3-B 얹음 A):
//   하우스는 학습 방식을 `Radio`(일반/고급) 로 고른다. 레시피는 N-단계이고 각 단계가
//   상태(idle/running/done/error)와 체이닝 게이트를 함께 표시해야 해서 `Radio` 로는
//   표현이 안 된다. → 하우스 어휘를 못 쓰는 유일한 상단 요소로 남긴다.
//
// ⚠️ 이 컴포넌트는 **선택만** 한다. 실행은 상단 버튼줄(`SDSTopButtons`)로 이동했다
//    (설계 §3-D 변경점 — recipe mode 의 실행/중지/시스템로그가 우측 모니터
//    `head-actions` 에서 `SimpleNav.topButtonList` 로 올라간 것이 이 위상의 핵심).
//
// 스타일: 과거 `RecipePipeline.module.scss`(→ `RecipeSections.module.scss` 로 이름만
//   이동, 규칙 무변경)의 `pipeline`/`connector`/`card`/`st-*` 를 그대로 쓴다 —
//   렌더 CSS 델타 0. `.pipeline` 이 `overflow-x:auto` 라 카드 포커스 링은 인셋형.

import { Fragment } from 'react';

import { derivePhaseStatus } from './payload/recipeState';

import classNames from 'classnames/bind';
import style from './RecipeSections.module.scss';

const sx = classNames.bind(style);

// 셸의 `fullWidthTop` 은 `.box` 위에 놓이므로 하우스 `.box .left`(margin-top:16px)와
// 같은 리듬을 인라인으로 준다 — SCSS 신규 규칙 0건.
const stepNavStyle = { marginTop: '16px' };

function RecipeStepNav({
  phases = [],
  selectedPhaseId,
  onSelect,
  activePhaseId,
  activePhaseStatus,
  donePhases,
}) {
  if (!phases.length) return null;

  return (
    <div style={stepNavStyle}>
      <div className={sx('pipeline')}>
        {phases.map((phase, idx) => {
          const st = derivePhaseStatus(
            phase,
            activePhaseId,
            activePhaseStatus,
            donePhases,
          );
          const selected = phase.id === selectedPhaseId;
          return (
            <Fragment key={phase.id}>
              {idx > 0 ? <div className={sx('connector')}>→</div> : null}
              <button
                type='button'
                className={sx('card', `st-${st}`, selected && 'selected')}
                onClick={() => onSelect(phase.id)}
                aria-pressed={selected}
              >
                <div className={sx('card-head')}>
                  <span className={sx('step-num')}>{idx + 1}</span>
                  <span className={sx('phase-label')}>{phase.label}</span>
                </div>
                {phase.description ? (
                  <div className={sx('step-target')}>{phase.description}</div>
                ) : null}
              </button>
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}

export default RecipeStepNav;
