// 하이퍼파라미터 섹션 — 하우스 `ModelRangeBar`(무수정) 재사용.
//
// ⚠️ present 키만 렌더(설계 §9 R8): `ModelRangeBar` 의 기본값이 `value = 0` 이라
//    `undefined` 를 넘기면 슬라이더가 0 으로 스냅되고, 그 값이 그대로 파트너 params 를
//    덮어쓴다. 그래서 `phase.params` 에 실제로 있는 키만 폼에 시드되고
//    (`buildPhaseForm`), 여기서도 `form[key] !== undefined` 인 spec 만 받는다.
// ⚠️ 값은 반드시 로컬 state(설계 §9 R10): 부모 `FineTuning.jsx:291,296` 이 SDS 분기에서
//    redux `range` 초기화 dispatch 를 early return 으로 건너뛴다 → `range[label]` 를
//    쓰면 전부 0/stale 이 된다.
// ⚠️ 한 섹션 안 `label` 유일성(R9): `ModelRangeBar` 가 `onChange(e, label)` /
//    `handleRefresh(label)` 로 label 을 식별 키로 쓴다. HP_SPECS 는 이미 유일.
//
// 스택은 하우스 유틸 `cx('flex-16')`(flex column gap 16). 과거 `mx('params-grid')`
// (grid minmax(320px,1fr)) 는 402px 좌측 컬럼에서 1열 gap 16 으로 동작했으므로
// 시각 결과가 동일하다 — 차용만 끊고 렌더는 그대로.

import ModelRangeBar from '../../ModelRangeBar/ModelRangeBar';

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';

const cx = classNames.bind(style);

/**
 * @param t     i18next t (호출부 주입 — 이 폴더 섹션들의 공통 관례)
 * @param specs [{ key, label, min, max, step }] — 호출부가 present 키로 필터해 넘긴다
 * @param form  현재 편집 폼(선택 phase)
 * @param onChange (key, numericValue) => void
 * @param title 섹션 제목(미지정 시 기본 '하이퍼파라미터' i18n 키)
 */
function RecipeHyperParamsSection({
  t,
  specs = [],
  form = {},
  onChange,
  title = null,
}) {
  if (!specs.length) return null;

  return (
    <>
      <div className={cx('title')}>
        {title ?? t('externalTraining.recipe.hyperParams.label')}
      </div>
      <div className={cx('flex-16')}>
        {specs.map((spec) => (
          <ModelRangeBar
            key={spec.key}
            label={spec.label}
            value={form[spec.key]}
            min={spec.min}
            max={spec.max}
            step={spec.step}
            onChange={(e) => onChange(spec.key, Number(e.target.value))}
          />
        ))}
      </div>
    </>
  );
}

export default RecipeHyperParamsSection;
