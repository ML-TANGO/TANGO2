// 학습 대상(freeze) 섹션 — 읽기전용 파생 표시(설계 §3-B 얹음 E).
//
// 입력이 아니다: `phase.params.phase`(train_type) 가 무엇을 학습/동결할지 결정하고
// 화면은 그 결과만 보여준다. 개별 on/off 토글은 지원하지 않는다(항목6).
// 하우스에 대응 개념이 없어 SDS 고유 `freeze-*` 시각언어를 유지하되, 섹션 제목은
// 하우스 어휘 `cx('title')` 로 치환했다(과거 `mx('section-label')` 차용 제거).
//
// MM 뷰(SDSMultimodalFineTuningView)도 같은 `freeze-banner` 마크업을 쓴다 —
// 두 SDS 화면의 시각언어를 일치시키는 지점이므로 클래스를 바꾸지 않는다.

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';
import localStyle from '../SDSFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

/**
 * @param t      i18next t (호출부 주입 — 이 폴더 섹션들의 공통 관례)
 * @param layers [{ name, note, cls }] — cls = frozen | trainable | lora
 * @param hint   편집 가능(idle) 상태에서만 넘기는 안내 문자열(없으면 미표시)
 */
function RecipeFreezeSection({ t, layers = [], hint = null }) {
  if (!layers.length) return null;

  return (
    <>
      <div className={cx('title')}>
        {t('externalTraining.recipe.trainTarget.label')}
      </div>
      <div className={lx('freeze-banner')}>
        {layers.map(({ name, note, cls }) => (
          <div
            key={`${name}-${note}`}
            className={lx('freeze-item', `freeze-item--${cls}`)}
            aria-label={`${name}: ${note}`}
          >
            <div>
              <div className={lx('freeze-name')}>{name}</div>
              <div className={lx('freeze-note')}>{note}</div>
            </div>
          </div>
        ))}
      </div>
      {hint ? <div className={lx('train-hint')}>{hint}</div> : null}
    </>
  );
}

export default RecipeFreezeSection;
