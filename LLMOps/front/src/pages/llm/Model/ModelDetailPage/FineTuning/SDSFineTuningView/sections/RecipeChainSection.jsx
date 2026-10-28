// 선행 phase 산출물(커밋) 선택 섹션.
//
// 레시피는 `chain_from` 으로 "이 phase 는 앞 phase 결과 위에서 학습한다" 를 못박고,
// `chain_inputs` 템플릿의 `{checkpoint_name}` 이 그 커밋명으로 치환된다. 원래는 **최신
// 커밋 하나**만 쓰도록 고정돼 있었는데, 완료 phase 를 다시 학습할 수 있게 되면서 한
// phase 에 커밋이 여러 개 쌓인다 — 재학습 결과가 나쁘면 이전 산출물로 되돌아갈 수단이
// 있어야 하므로 여기서 고른다. 기본값은 목록 0번(최신).
//
// ⚠️ 2단 프로토콜의 **1단 입력**(설계 §9 R2): 고른 값은 `mergePhaseParams({ chainSelection })`
//    가 FE-내부 마커 `params._chain_commit` 로 심고, 부모 `launchPhase` 의 `applyChaining`
//    이 커밋명 규약(`{phase.id}-{YYYYMMDD}-{HHMMSS}`)으로 검증한 뒤 치환·제거한다.
//    이 컴포넌트는 커밋명 문자열을 그대로 넘기는 것 외에 어떤 변형도 하지 않는다.

import { Selectbox } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';

const cx = classNames.bind(style);

const selectboxStyle = {
  selectboxForm: { width: '100%' },
  listForm: { width: '100%' },
};

/**
 * @param t        i18next t (호출부 주입 — 이 폴더 섹션들의 공통 관례)
 * @param commits  선행 phase 커밋명 배열(최신 우선). 0~1개면 고를 게 없어 렌더하지 않는다.
 * @param value    선택된 커밋명 ('' = 최신)
 * @param onChange (value: string) => void
 */
function RecipeChainSection({ t, commits = [], value = '', onChange }) {
  if (commits.length < 2) return null;

  const options = commits.map((name, i) => ({
    label:
      i === 0 ? `${name} (${t('externalTraining.recipe.chain.latest')})` : name,
    value: name,
  }));
  const selected = options.find((o) => o.value === value) || options[0];

  return (
    <>
      <div className={cx('title')}>
        {t('externalTraining.recipe.chain.label')}
      </div>
      <Selectbox
        list={options}
        selectedItem={selected}
        onChange={(item) => onChange(item.value)}
        scrollAutoFocus={true}
        customStyle={selectboxStyle}
      />
    </>
  );
}

export default RecipeChainSection;
