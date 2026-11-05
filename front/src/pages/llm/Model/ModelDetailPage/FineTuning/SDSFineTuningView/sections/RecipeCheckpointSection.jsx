// 체크포인트 설정 섹션 (설계 §3-B 얹음 B / §2-A #9·#10).
//
// 출력 이름(`output_checkpoint_name`) + step 제어 4키. 하우스에는 "출력 이름" 개념이
// 없다(하우스는 커밋 모달이 이름을 받는다) → 얹는 섹션으로 남기되 컨트롤은 조나단
// 공용 `InputText` + 하우스 `ModelRangeBar` 만 쓴다(어휘 위반 아님, 설계 §2-A #9).
// 라벨은 하우스 관행대로 컨트롤 **위**에 `cx('title')` 로 둔다 — 과거 인라인
// `ckpt-name-row`/`ckpt-name-label` 자체 클래스 제거.
//
// ⚠️ 계약(설계 §9 R1 / 결정 D1): `save_steps`/`eval_steps`/`logging_steps`/
//    `save_total_limit` 4키는 실 레시피(eva-vlm-train v11)에 **없어서** FE 가
//    `CKPT_DEFAULTS` 로 항상 주입한다. 이 동작은 **의도적으로 보존**한다 —
//    차분 검증(`/tmp/verify-sds-payload.mjs`)에 전용 케이스가 있어 무심코 "정리"
//    하면 실패로 잡힌다. 여기서 슬라이더를 빼면 값은 계속 주입되지만 사용자가
//    조정할 수 없게 되므로 4키 전부 노출을 유지한다.
// ⚠️ 빈 이름이 필수키를 덮지 않는다 — `mergePhaseParams` 가 trim 후 비어있지 않을
//    때만 `output_checkpoint_name` 을 오버레이한다(순수 함수 소관, 여기서 검증 X).

import { InputText } from '@jonathan/ui-react';

import ModelRangeBar from '../../ModelRangeBar/ModelRangeBar';

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';

const cx = classNames.bind(style);

const fullWidthStyle = { width: '100%' };

/**
 * @param t        i18next t (호출부 주입 — 이 폴더 섹션들의 공통 관례)
 * @param name     output_checkpoint_name 현재값
 * @param onChangeName (string) => void
 * @param specs    CKPT_NUM_SPECS
 * @param form     현재 편집 폼(선택 phase)
 * @param onChange (key, numericValue) => void
 */
function RecipeCheckpointSection({
  t,
  name = '',
  onChangeName,
  specs = [],
  form = {},
  onChange,
}) {
  return (
    <>
      <div className={cx('title')}>
        {t('externalTraining.recipe.checkpoint.label')}
      </div>
      <div className={cx('flex-16')}>
        <div>
          <div className={cx('title')}>
            {t('externalTraining.recipe.checkpointName.label')}
          </div>
          <InputText
            size='medium'
            value={name}
            onChange={(e) => onChangeName(e.target.value)}
            placeholder='output_checkpoint_name'
            disableClearBtn
            customStyle={fullWidthStyle}
          />
        </div>
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

export default RecipeCheckpointSection;
