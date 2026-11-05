// Components
import { Selectbox } from '@jonathan/ui-react';
import CardList from './CardList';

// CSS module
import classNames from 'classnames/bind';
import style from './BuiltInModelSelectBox.module.scss';
const cx = classNames.bind(style);

const BuiltInModelSelectBox = ({
  isTraining,
  deploymentType,
  builtInType,
  builtInTypeOptions,
  builtInFilter,
  builtInFilterOptions,
  thumbnailList,
  modelOptions,
  model,
  jobGroupOptions,
  jobGroup,
  groupNumberOptions,
  groupNumber,
  checkpointOptions,
  checkpoint,
  runCodeOptions,
  runCode,
  selectInputHandler,
  selectBuiltInModelHandler,
  readOnly,
  onSearch,
  scroll,
  t,
}) => {
  return (
    <div className={cx('model-select-box')}>
      {deploymentType === 'built-in' && (
        <div className={cx('row')}>
          {Array.isArray(builtInTypeOptions) ? (
            <>
              <p className={cx('step')}>
                {t('builtInModelSelect.step1.label')}
              </p>
              <div className={cx('float-box')}>
                <Selectbox
                  size='medium'
                  list={builtInTypeOptions}
                  selectedItem={!builtInType ? undefined : builtInType}
                  placeholder={t('builtInType.placeholder')}
                  isReadOnly={readOnly}
                  onChange={(value) => {
                    selectInputHandler('builtInType', value);
                  }}
                  scrollAutoFocus={true}
                />
                <Selectbox
                  size='medium'
                  list={builtInFilterOptions}
                  selectedItem={builtInFilter}
                  placeholder={t('builtInModelCategory.placeholder')}
                  isReadOnly={readOnly}
                  // isDisable={
                  //   !builtInType ||
                  //   (builtInType && builtInType.value === 'custom')
                  // }
                  isDisable={true}
                  onChange={(value) => {
                    selectInputHandler('builtInFilter', value);
                  }}
                  t={t}
                  scrollAutoFocus={true}
                />
              </div>
            </>
          ) : (
            <>
              <p className={cx('step')}>
                {t('builtInModelCategorySelect.step1.label')}
                -- TEST 중 --
              </p>
              <div className={cx('row')}>
                <Selectbox
                  size='medium'
                  list={builtInFilterOptions}
                  selectedItem={builtInFilter}
                  placeholder={t('builtInModelCategory.placeholder')}
                  isReadOnly={readOnly}
                  // isDisable={
                  //   !builtInType ||
                  //   (builtInType && builtInType.value === 'custom')
                  // }
                  isDisable={true}
                  onChange={(value) => {
                    selectInputHandler('builtInFilter', value);
                  }}
                  t={t}
                  scrollAutoFocus={true}
                />
              </div>
            </>
          )}
        </div>
      )}
      <div className={cx('row')}>
        <p className={cx('step')}>
          {isTraining
            ? t('trainingModelSelect.step2.label')
            : t('modelSelect.step2.label', {
                number: deploymentType === 'custom' ? '1' : '2',
              })}
        </p>
        {deploymentType === 'built-in' ? (
          <CardList
            builtInType={builtInType}
            jobGroupOptions={jobGroupOptions}
            modelOptions={modelOptions}
            thumbnailList={thumbnailList}
            model={model}
            selectBuiltInModelHandler={selectBuiltInModelHandler}
            scroll={scroll}
            readOnly={readOnly}
            t={t}
            onSearch={onSearch}
          />
        ) : (
          <Selectbox
            type='search'
            size='medium'
            list={modelOptions}
            selectedItem={model}
            placeholder={t('modelSelect.placeholder')}
            onChange={(value) => {
              selectInputHandler('model', value);
            }}
            isDisable={true}
            customStyle={{
              fontStyle: {
                selectbox: {
                  color: '#121619',
                  textShadow: 'None',
                },
              },
            }}
            scrollAutoFocus={true}
          />
        )}
      </div>
      {deploymentType === 'custom' && (
        <div className={cx('row')}>
          <p className={cx('step')}>{t('runCodeSelect.label')}</p>
          <div>
            {model ? (
              <Selectbox
                type='search'
                size='medium'
                list={runCodeOptions}
                selectedItem={runCode}
                placeholder={t('runCode.placeholder')}
                onChange={(value) => {
                  selectInputHandler('runCode', value);
                }}
                customStyle={{
                  fontStyle: {
                    selectbox: {
                      color: '#121619',
                      textShadow: 'None',
                    },
                  },
                }}
                scrollAutoFocus={true}
              />
            ) : (
              <div className={cx('empty-message')}>
                {t('runCodeSelect.empty.message')}
              </div>
            )}
          </div>
        </div>
      )}
      {jobGroupOptions &&
        deploymentType === 'built-in' &&
        builtInType &&
        builtInType.value === 'custom' && (
          <div className={cx('row')}>
            <p className={cx('step')}>{t('modelSelect.step3.label')}</p>
            <div className={cx('job-box')}>
              <div className={cx('group')}>
                <Selectbox
                  size='medium'
                  list={jobGroupOptions}
                  selectedItem={jobGroup}
                  placeholder={t('jobGroup.placeholder')}
                  isDisable={!model}
                  onChange={(value) => {
                    selectInputHandler('jobGroup', value);
                  }}
                  customStyle={{ globalForm: { flex: 2 } }}
                  t={t}
                  scrollAutoFocus={true}
                />
                <Selectbox
                  size='medium'
                  list={groupNumberOptions}
                  selectedItem={groupNumber}
                  placeholder={t('groupNumber.placeholder')}
                  isDisable={!jobGroup}
                  onChange={(value) => {
                    selectInputHandler('groupNumber', value);
                  }}
                  customStyle={{ globalForm: { flex: 1 } }}
                  t={t}
                  scrollAutoFocus={true}
                />
              </div>
              <Selectbox
                size='medium'
                list={checkpointOptions}
                selectedItem={checkpoint}
                placeholder={t('checkpoint.placeholder')}
                isDisable={!groupNumber}
                onChange={(value) => {
                  selectInputHandler('checkpoint', value);
                }}
                t={t}
                scrollAutoFocus={true}
              />
            </div>
          </div>
        )}
    </div>
  );
};

export default BuiltInModelSelectBox;
