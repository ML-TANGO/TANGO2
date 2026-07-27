// i18n
import { useTranslation } from 'react-i18next';

import { InputText, Selectbox } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ModelSelector from '@src/components/ModelSelector/ModelSelector';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './EvalProjectFormModal.module.scss';

const cx = classNames.bind(style);

// 평가 유형 3종 — label 은 i18n 키(Radio 가 isTranLabel 로 내부 t() 처리). 기존 evaluation.mode.* 재사용.
const TYPE_OPTIONS = [
  { label: 'evaluation.mode.benchmark.title', value: 'benchmark' },
  { label: 'evaluation.mode.judge.title', value: 'judge' },
  { label: 'evaluation.mode.expert.title', value: 'expert' },
];

// 새 평가 프로젝트 생성 모달(프레젠테이셔널) — 학습/배포 모달과 동일한 프레임/필드 규격.
//   NewStyleModalFrame(664px·resize·minimize) + InputBoxWithLabel + 디자인시스템 컴포넌트.
//   필드: 이름(InputText) → 평가유형(Radio) → 모델(ModelSelector) → 데이터셋(Selectbox 검색형, 단일).
//   상태·검증·submit 은 컨테이너 소유(BE 계약: name/model_id/dataset_ids/eval_type).
function EvalProjectFormModal({
  type,
  data,
  workspaceId,
  validate,
  name,
  setName,
  evalType,
  setEvalType,
  modelId,
  setModelId,
  datasetOptions,
  selectedDataset,
  onSelectDataset,
  onSubmit,
}) {
  const { t } = useTranslation();
  const { submit, cancel } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => await onSubmit(),
  };

  const title = t('evaluation.project.createTitle');

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={title}
      headerTitle={title}
      submitBtnTestId='create-eval-project-btn'
      customStyle={{ width: '664px' }}
    >
      <div className={cx('form')}>
        {/* ** 이름 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.project.name')}
            labelSize='large'
            disableErrorMsg
          >
            <InputText
              size='medium'
              placeholder={t('evaluation.project.namePlaceholder')}
              name='name'
              value={name}
              onChange={(e) => setName(e.target.value)}
              onClear={() => setName('')}
              options={{ maxLength: 100 }}
              autoFocus
              disableLeftIcon
              testId='eval-project-name-input'
              customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
            />
          </InputBoxWithLabel>
        </div>

        {/* ** 평가 유형 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.project.selectType')}
            labelSize='large'
            disableErrorMsg
          >
            <Radio
              name='evalType'
              value={evalType}
              options={TYPE_OPTIONS}
              onChange={(e) => setEvalType(e.target.value)}
              isLabelColor
            />
          </InputBoxWithLabel>
        </div>

        {/* ** 모델 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.selectModel')}
            labelSize='large'
            disableErrorMsg
          >
            <ModelSelector
              wid={workspaceId}
              selected={modelId}
              onSelect={(id) => setModelId(id)}
            />
          </InputBoxWithLabel>
        </div>

        {/* ** 데이터셋 (단일 선택 — BE dataset_ids max_length=1) ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.selectDatasets')}
            labelSize='large'
            disableErrorMsg
          >
            {datasetOptions.length === 0 ? (
              <p className={cx('empty')}>{t('evaluation.noDatasets')}</p>
            ) : (
              <Selectbox
                type='search'
                size='large'
                list={datasetOptions}
                placeholder={t('evaluation.searchDataset')}
                selectedItem={selectedDataset}
                onChange={(item) => onSelectDataset(item)}
                scrollAutoFocus={true}
              />
            )}
          </InputBoxWithLabel>
        </div>
      </div>
    </NewStyleModalFrame>
  );
}

export default EvalProjectFormModal;
