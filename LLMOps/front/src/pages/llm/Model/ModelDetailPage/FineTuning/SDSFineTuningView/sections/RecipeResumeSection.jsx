// 이어서 학습(warm start) 섹션 — 설계 §3-B 얹음 C / §2-A #11 / §7.
//
// 왜 하우스 `FINETUNING_COMMIT_LOAD` 모달을 재사용하지 않는가:
//   하우스의 "커밋 불러오기" 는 **커밋** 단위인데 external 체크포인트는
//   `<commit>/checkpoint-<step>` 단위다(엔진이 step 마다 저장). 모달의 목록 계약과
//   맞지 않아 조나단 공용 `Selectbox` 로 좌측 섹션에 남긴다.
//
// ⚠️ 2단 프로토콜의 **1단 입력**(설계 §9 R2): 여기서 고른 값은 그대로
//    `mergePhaseParams({ resumeSelection })` 에 들어가 FE-내부 마커
//    `params._resume_checkpoint` 로 **심어지고**, 부모 `launchPhase` 의
//    `applyChaining` 이 그것을 `resume_lora_path`/`projector_path` 로 **번역·제거**한다.
//    이 컴포넌트는 값을 문자열로 전달하는 것 외에 어떤 변형도 하지 않는다 —
//    포맷(`<commit>/checkpoint-<step>`)을 여기서 손대면 번역이 깨진다.

import { Selectbox } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';
import localStyle from '../SDSFineTuningView.module.scss';

const cx = classNames.bind(style);
const lx = classNames.bind(localStyle);

const selectboxStyle = {
  selectboxForm: { width: '100%' },
  listForm: { width: '100%' },
};

/**
 * @param t       i18next t (호출부 주입 — 이 폴더 섹션들의 공통 관례)
 * @param options [{ label, value }] — 0번이 '처음부터'(value '')
 * @param value   선택된 value ('' = 처음부터)
 * @param onChange (value: string) => void
 */
function RecipeResumeSection({ t, options = [], value = '', onChange }) {
  if (!options.length) return null;

  return (
    <>
      <div className={cx('title')}>
        {t('externalTraining.recipe.resume.label')}
      </div>
      <Selectbox
        list={options}
        selectedItem={options.find((o) => o.value === value) || options[0]}
        onChange={(item) => onChange(item.value)}
        customStyle={selectboxStyle}
      />
      <div className={lx('train-hint')}>
        {t('externalTraining.recipe.resume.hint')}
      </div>
    </>
  );
}

export default RecipeResumeSection;
