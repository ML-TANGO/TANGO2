import { Selectbox } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from '../../FineTuning.module.scss';

const cx = classNames.bind(style);

const fullWidthStyle = { width: '100%' };

// 학습 데이터셋 선택 섹션.
//
// 레시피는 phase 마다 `_dataset`(예약키)으로 마운트할 워크스페이스 데이터셋을 못박아 둔다.
// 학습/평가 분할(sds_train 9k ↔ sds_eval 1k)이 생기면서 "이 phase 가 무엇으로 학습했는가"가
// 결과의 신뢰도를 좌우하게 됐는데, 매니페스트를 고치지 않으면 바꿀 수 없어 화면에 올린다.
//   ⚠️ 데이터셋을 바꾸면 `/dataset/<이름>` 을 가리키는 경로 파라미터(data_path·image_dir 등)도
//      같이 따라가야 한다 — 그 재작성은 순수 모듈(recipeParams.applyDatasetChoice)이 한다.
//      여기서는 이름만 고른다.
function RecipeDatasetSection({ t, options = [], value = '', onChange }) {
  const selected = options.find((item) => item.value === value) || null;
  return (
    <>
      <div className={cx('title')}>
        {t('externalTraining.recipe.dataset.label')}
      </div>
      <Selectbox
        type='search'
        list={options}
        selectedItem={selected}
        placeholder={t('select.label')}
        onChange={(item) => onChange(item.value)}
        scrollAutoFocus={true}
        customStyle={{ selectboxForm: fullWidthStyle, listForm: fullWidthStyle }}
      />
    </>
  );
}

export default RecipeDatasetSection;
