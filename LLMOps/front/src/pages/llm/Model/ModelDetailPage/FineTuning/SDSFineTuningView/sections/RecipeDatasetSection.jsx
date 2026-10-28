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
//   ⚠️ 데이터셋을 바꾸면 `/dataset/<이름>` 을 가리키는 경로 파라미터(image_dir 등)도 같이
//      따라가야 한다 — 그 재작성은 순수 모듈(recipeParams.applyDatasetChoice)이 한다.
//
// 학습 파일(`data_path`)은 접두사 재작성으로 못 맞춘다. 데이터셋마다 파일명이 다르기
// 때문이다(sds/sds_train_ko.json 100건 ↔ sds_train/sds_train_ko_9k.json 9,000건).
// 이름만 갈아끼우면 없는 파일을 가리켜, 실제로 phase 4 가 9천 건 대신 100 건(매니페스트에
// 박힌 이미지 내부 데모 파일)으로 조용히 학습된 적이 있다. 그래서 데이터셋 안에 **실재하는**
// json 만 골라 담은 두 번째 선택기를 둔다.
function RecipeDatasetSection({
  t,
  options = [],
  value = '',
  onChange,
  fileOptions = [],
  fileValue = '',
  onChangeFile,
  fileLoading = false,
}) {
  const selected = options.find((item) => item.value === value) || null;
  const selectedFile =
    fileOptions.find((item) => item.value === fileValue) || null;
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
      {onChangeFile ? (
        <>
          <div className={cx('title')}>
            {t('externalTraining.recipe.datasetFile.label')}
          </div>
          <Selectbox
            type='search'
            list={fileOptions}
            selectedItem={selectedFile}
            placeholder={
              fileLoading
                ? t('externalTraining.recipe.datasetFile.loading')
                : t('externalTraining.recipe.datasetFile.placeholder')
            }
            onChange={(item) => onChangeFile(item.value)}
            scrollAutoFocus={true}
            customStyle={{
              selectboxForm: fullWidthStyle,
              listForm: fullWidthStyle,
            }}
          />
        </>
      ) : null}
    </>
  );
}

export default RecipeDatasetSection;
