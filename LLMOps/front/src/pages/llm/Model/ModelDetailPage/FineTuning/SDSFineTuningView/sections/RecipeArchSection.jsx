// 모델 구조 · 프로젝터 섹션 (설계 §3-B 얹음 D / §2-A #12·#13·#14).
//
// ⚠️ **백엔드 미전송 — 시각화 전용.** 실제 projector 구조는 SDS 컨테이너(recipe/엔진)가
//    결정하고, 다른 구조/파라미터는 ETRI 가 컨테이너 고도화 시 탑재한다. 여기서 고른
//    값은 도식 라벨만 바꾸며 `phase.params` 에 절대 섞이지 않는다(payload 계약).
//
// 유지 결정(설계 §11 D6 = 잔여 미결, 구현 중 결정):
//   - 5종 선택을 하우스 `Radio` 로 치환하는 안은 **채택하지 않았다.** 402px 좌측 컬럼에
//     5+3 개 옵션을 라디오 행으로 펼치면 세로가 크게 늘고, 이 블록은 학습에 영향을 주지
//     않는 부차 시각화다. 칩 버튼은 고정 열 grid 로 배치되고 `focus-ring` 이 이미
//     걸려 있어 접근성도 확보돼 있다. 어휘 정렬 대상은 **섹션 제목**
//     (`mx('section-label')` → `cx('title')`)만.
//   - 설계 §3-B 의 "접힘 기본" 도 적용하지 않았다 — 접기 토글 추가는 동작 변경이며
//     이 위상의 불변식("순수 표현 재배치")을 벗어난다. Phase 5 후보.
//
// ⚠️ R13: '크게 보기' 는 플랫폼 모달 시스템(`openModal`) 밖의 자체 backdrop 이다.
//    Esc 닫기 + body 스크롤락은 호출부(컨테이너)의 effect 가 담당한다 — 플랫폼
//    ModalFrame 으로의 이관은 별도 항목.

import { ButtonV2 } from '@jonathan/ui-react';

import MultimodalArchDiagram from './MultimodalArchDiagram';

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';
import sectionStyle from '../RecipeSections.module.scss';

const cx = classNames.bind(style);
const sx = classNames.bind(sectionStyle);

// 항목8: projector 구조(표시용) — 현재 MLP-2 고정.
const PROJECTOR_TYPES = [
  { value: 'mlp2', label: 'MLP-2' },
  { value: 'linear', label: 'Linear' },
  { value: 'mlp3', label: 'MLP-3' },
  { value: 'xattn', label: 'Cross-Attention' },
  { value: 'qformer', label: 'Q-Former' },
];

export const FIXED_PROJ = 'mlp2';

function RecipeArchSection({
  t,
  projType,
  onProjType,
  mlpHidden,
  onMlpHidden,
  xAttnHeads,
  onXAttnHeads,
  qTokens,
  onQTokens,
  diagramOpen,
  onOpenDiagram,
  onCloseDiagram,
}) {
  const chipRow = (label, values, current, onPick, format) => (
    <div className={sx('proj-param-row')}>
      <span className={sx('proj-param-label')}>{label}</span>
      <div className={sx('proj-selector')}>
        {values.map((v) => (
          <button
            key={v}
            type='button'
            className={sx('proj-btn', current === v && 'active')}
            onClick={() => onPick(v)}
            aria-pressed={current === v}
          >
            {format ? format(v) : v}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <>
      <div className={cx('title')}>
        {t('externalTraining.recipe.arch.label')}
      </div>
      {/* 종류 5종 = 고정 2열 grid(`proj-type-selector`) — 선택해도 배열이 안 튄다. */}
      <div className={sx('proj-type-selector')}>
        {PROJECTOR_TYPES.map((p) => (
          <button
            key={p.value}
            type='button'
            className={sx('proj-btn', p.value === projType && 'active')}
            onClick={() => onProjType(p.value)}
            aria-pressed={p.value === projType}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* 프로젝터 타입별 파라미터(시각화 전용) — 도식 라벨에 반영.
          래퍼(`proj-params`)가 최대 변형 기준 높이를 미리 잡는다 → 'Linear'(파라미터
          없음)로 바꿔도 아래 도식이 위로 튀지 않는다. 해당 없는 파라미터를 disabled
          로 항상 노출하는 안은 쓰지 않았다 — 이 5종은 payload 에 안 들어가므로
          전송되지 않는 값이 컨트롤처럼 보이는 편이 오히려 오해를 만든다. */}
      <div className={sx('proj-params')}>
        {(projType === 'mlp2' || projType === 'mlp3') &&
          chipRow('Hidden Dim', [1024, 2048, 4096], mlpHidden, onMlpHidden)}
        {projType === 'xattn' &&
          chipRow(
            'Attn Heads',
            [4, 8, 16],
            xAttnHeads,
            onXAttnHeads,
            (h) => `${h} heads`,
          )}
        {projType === 'qformer' &&
          chipRow(
            'Query Tokens',
            [16, 32, 64],
            qTokens,
            onQTokens,
            (q) => `${q} tokens`,
          )}
      </div>

      <div className={sx('diagram-head')}>
        <ButtonV2
          type='outline'
          colorType='blue'
          size='s'
          label={t('externalTraining.recipe.arch.expand.label')}
          onClick={onOpenDiagram}
        />
      </div>

      <MultimodalArchDiagram
        projType={projType}
        mlpHidden={mlpHidden}
        xAttnHeads={xAttnHeads}
        qTokens={qTokens}
      />

      {diagramOpen && (
        <div className={sx('diagram-modal-backdrop')} onClick={onCloseDiagram}>
          <div
            className={sx('diagram-modal')}
            role='dialog'
            aria-modal='true'
            aria-label={t('externalTraining.recipe.arch.label')}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={sx('diagram-modal-head')}>
              <span className={sx('diagram-modal-title')}>
                {t('externalTraining.recipe.arch.label')}
              </span>
              <button
                type='button'
                className={sx('diagram-modal-close')}
                onClick={onCloseDiagram}
                aria-label={t('close.label')}
              >
                ✕
              </button>
            </div>
            <div className={sx('diagram-modal-body')}>
              <MultimodalArchDiagram
                projType={projType}
                mlpHidden={mlpHidden}
                xAttnHeads={xAttnHeads}
                qTokens={qTokens}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default RecipeArchSection;
