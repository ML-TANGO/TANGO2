import { withTranslation } from 'react-i18next';

import { InputNumber, InputText, Selectbox } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import GpuNodeSelectBox from '@src/components/molecules/GpuNodeSelectBox';
import InfiniteScrollDropDown from '@src/components/molecules/InfiniteScrollDropDown';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiText from '@src/components/molecules/MultiText';

// Components
import NewStyleModalFrame from '../NewStyleModalFrame';
import ParameterInput from './ParameterInput';

// CSS module
import classNames from 'classnames/bind';
import style from './JobCreateFormModal.module.scss';

const cx = classNames.bind(style);

const JobCreateFormModal = ({
  validate,
  data,
  type: modalType, // modal type
  builtInModelName, // built in model name
  trainingType, // training type
  name,
  nameError,
  runcodeName,
  runcodeNameError,
  runcodeOptions,
  // hpsResultOptions,
  // hpsResult,
  loadFile,
  gpuModels,
  gpuInputValues,
  gpuSelectedOptions,
  gpuAllocate,
  onChangeGpuInputValue,
  parameterValues,
  parameterError,
  onAdd,
  onRemove,
  onChangeParameter,
  onChangeBuiltInParameter,
  textInputHandler,
  imageOptions,
  selectedImage,
  selectInputHandler,
  onSubmit,
  searchSelectHandler,
  t,
  footerMessage,
  gpuClusterOption,
  gpuClusterSelectedOption,
  handleGpuClusterOption,
  distributionLearningOption,
  distributionLearningSelectedOption,
  handleDistributionLearningOption,
  gpuClusterList,
  handleSelectedGpuCluster,
  gpuUsingError,
  gpuClusterType,
  selectedGpuClusterType,
  handleGpuClusterType,
  distributedConfigFileList,
  selectedDistributedConfigFile,
  handleDistributedConfigFileSelect,
  podGpuGcd,
  trainingInfo,
  datasetList,
  selectedDataset: selectedDatasetList,
  handleDatasetList,
}) => {
  const transformDataList = datasetList.map((info) => ({
    ...info,
    label: info.name,
    value: info.id,
  }));

  const { submit, cancel } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {
      if (modalType === 'CREATE_HPS_GROUP' || modalType === 'ADD_HPS') {
        const res = await onCreate();
        return res;
      }
      const res = await onCreate();
      return res;
    },
  };

  let titleTKey = '';
  if (modalType === 'CREATE_JOB') titleTKey = 'createJobForm.title.label';
  else if (modalType === 'CREATE_HPS_GROUP')
    titleTKey = 'createHPSForm.title.label';
  else if (modalType === 'ADD_HPS') titleTKey = 'addHPSForm.title.label';

  const onCreate = async () => {
    let parserList = {};

    return await onSubmit(submit.func, parserList);
  };

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={modalType}
      validate={validate}
      // validate={validate && submitBtn}
      isResize={true}
      isMinimize={true}
      title={`${t(titleTKey)}${
        trainingType === 'built-in' ? ` - ${builtInModelName}` : ''
      }`}
      footerMessage={footerMessage}
      customStyle={{
        width: '664px',
      }}
    >
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={
              modalType === 'CREATE_JOB'
                ? t('jobName.label')
                : t('hpsName.label')
            }
            labelSize='large'
            errorMsg={t(nameError)}
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <InputText
              size='medium'
              placeholder={
                modalType === 'CREATE_JOB'
                  ? t('jobName.placeholder')
                  : t('hpsName.placeholder')
              }
              value={name}
              name='name'
              onChange={textInputHandler}
              onClear={() =>
                textInputHandler({ target: { value: '', name: 'name' } })
              }
              status={nameError ? 'error' : 'default'}
              options={{ maxLength: 50 }}
              isReadOnly={modalType === 'ADD_HPS'}
              isLowercase
              disableLeftIcon
              disableClearBtn={false}
              autoFocus
              customStyle={{
                fontSize: '14px',
              }}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row', 'docker')}>
          <InputBoxWithLabel
            labelText={t('dockerImage.label')}
            labelSize='large'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <Selectbox
              size='medium'
              placeholder={t('dockerImage.placeholder')}
              list={imageOptions}
              selectedItem={selectedImage}
              onChange={(v) => {
                selectInputHandler('selectedImage', v);
              }}
              customStyle={{
                globalForm: {
                  fontSize: '14px',
                },
                fontStyle: {
                  selectbox: {
                    color: '#121619',
                    textShadow: 'None',
                    fontSize: '14px',
                    fontFamily: 'SpoqaM',
                  },
                  list: {
                    fontSize: '14px',
                  },
                },
              }}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('docker-gpu-row')}>
          <div className={cx('row', 'docker')}>
            <InputBoxWithLabel
              labelText={t('dataset.label')}
              labelSize='large'
              disableErrorMsg
            >
              <Selectbox
                size='medium'
                placeholder={t('collect.dataset.placeholder')}
                list={transformDataList}
                selectedItem={selectedDatasetList}
                onChange={handleDatasetList}
                customStyle={{
                  globalForm: {
                    fontSize: '14px',
                  },
                  fontStyle: {
                    selectbox: {
                      color: '#121619',
                      textShadow: 'None',
                      fontSize: '14px',
                      fontFamily: 'SpoqaM',
                    },
                    list: {
                      fontSize: '14px',
                    },
                  },
                }}
              />
            </InputBoxWithLabel>
          </div>
          {gpuModels?.instanceType === 'GPU' && (
            <div className={cx('row', 'gpu')}>
              <InputBoxWithLabel
                labelText={`${t('gpuAllocation.label')}`}
                labelSize='large'
                labelDescText={`${gpuModels?.name}`}
                labelDescStyle={{
                  color: 'rgba(116, 116, 116, 1)',
                  marginLeft: '6px',
                  fontSize: '14px',
                }}
                disableErrorMsg
              >
                <InputNumber
                  name='gpuInput'
                  placeholder={`${t('currentAvailableCount')} : ${
                    gpuModels?.total
                  }`}
                  min={0}
                  max={gpuModels?.total}
                  value={gpuAllocate}
                  onChange={(e) => {
                    let inputValue = e.value;
                    if (gpuModels?.total < inputValue) {
                      inputValue = gpuModels?.total;
                    }
                    onChangeGpuInputValue(inputValue);
                  }}
                  customStyle={{
                    fontSize: '14px',
                  }}
                />
              </InputBoxWithLabel>
            </div>
          )}
        </div>

        {gpuAllocate > 1 && (
          <div className={cx('gpu-option-row')}>
            {/** 분산 학습 백엔드 */}
            {gpuAllocate > 1 && (
              <div className={cx('radio-wrap')}>
                <InputBoxWithLabel
                  labelText={t('distributedLearningBackend.label')}
                  labelSize='large'
                  disableErrorMsg
                >
                  <Radio
                    options={distributionLearningOption}
                    onChange={(e) =>
                      handleDistributionLearningOption(e.currentTarget.value)
                    }
                    value={distributionLearningSelectedOption}
                    isShowAllDesc={false}
                    isLabelColor={true}
                    customStyle={{ gap: '24px' }}
                  />
                </InputBoxWithLabel>
                <div className={cx('cluster-info')}>
                  <div>
                    {distributionLearningSelectedOption === 1 &&
                      `[권장] ${t('Nccl.desc')}`}
                    {distributionLearningSelectedOption === 2 && (
                      <span className={cx('not-recommand')}>
                        {t('Mpi.desc')}
                      </span>
                    )}
                    {distributionLearningSelectedOption === 0 && (
                      <span className={cx('not-recommand')}>
                        {t('etc.desc')}
                      </span>
                    )}
                  </div>

                  <div>
                    {distributionLearningSelectedOption === 1 && (
                      <div className={cx('warning')}>{`[주의] ${t(
                        'createjobNcclWarning',
                      )}`}</div>
                    )}
                    {distributionLearningSelectedOption === 2 && (
                      <div className={cx('warning')}>{`${t(
                        'Mpi.warning',
                      )}`}</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className={cx('divider-line')}></div>

            {/** 분산학습 호스트 설정 파일 선택 */}
            {gpuAllocate > 1 && (
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={t('hostOptionFile.label')}
                  labelSize='large'
                  disableErrorMsg
                  labelDescText={'(EX) ./hostfile'}
                  labelDescStyle={{
                    fontSize: '16px',
                    fontFamily: 'SpoqaM',
                    marginLeft: '4px',
                  }}
                >
                  <InfiniteScrollDropDown
                    placeholder={t('hostOptionFile.placeholder')}
                    handleSelectOption={(selectItem) => {
                      handleDistributedConfigFileSelect(selectItem);
                    }}
                    value={
                      selectedDistributedConfigFile ?? { label: '', value: '' }
                    }
                    tid={Number(data.data.tid)}
                    listCustomStyle={{ maxHeight: '200px', overflow: 'auto' }}
                    isCloseBorder={false}
                    isDist={true}
                  />
                </InputBoxWithLabel>
              </div>
            )}

            <div className={cx('divider-line', 'top')}></div>

            {/** GPU 클러스터 설정 */}
            {gpuAllocate > 1 && (
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={t('gpuClusterOption')}
                  labelSize='large'
                >
                  <Radio
                    options={gpuClusterOption}
                    customStyle={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                    }}
                    onChange={(e) =>
                      handleGpuClusterOption(e.currentTarget.value)
                    }
                    value={gpuClusterSelectedOption}
                    isShowAllDesc={false}
                    isLabelColor={true}
                  />
                </InputBoxWithLabel>
              </div>
            )}
            {/** GPU 클러스터 선택 리스트 GPU 할당 2개 이상일때 보여줘야한다. */}
            {gpuAllocate > 1 && gpuClusterSelectedOption === 0 && (
              <div className={cx('row')}>
                <GpuNodeSelectBox
                  gpuClusterList={gpuClusterList}
                  handleSelectedGpuCluster={handleSelectedGpuCluster}
                  gpuUsingError={gpuUsingError}
                  podGpuGcd={podGpuGcd}
                  isShowPodGpuGcd={true}
                />
              </div>
            )}

            {/** GPU 클러스터 유형 */}
            {gpuAllocate > 1 && gpuClusterType.length ? (
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={t('gpuClusterCategory.label')}
                  labelSize='large'
                >
                  <Radio
                    options={gpuClusterType}
                    customStyle={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                    }}
                    onChange={(e) =>
                      handleGpuClusterType(e.currentTarget.value)
                    }
                    value={selectedGpuClusterType}
                    isLabelColor={true}
                  />
                </InputBoxWithLabel>
              </div>
            ) : (
              <div></div>
            )}
          </div>
        )}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={`${t('runCode.label')}`}
            labelSize='large'
            errorMsg={t(runcodeNameError)}
            labelDescText={`(EX) /train.py`}
            labelDescStyle={{
              color: 'rgba(116, 116, 116, 1)',
              marginLeft: '6px',
              fontSize: '14px',
            }}
            style={{ marginBottom: '32px' }}
            disableErrorMsg
          >
            <InfiniteScrollDropDown
              placeholder={t('runCode.placeholder')}
              handleSelectOption={(selectItem) => {
                searchSelectHandler(selectItem, 'runcodeName');
              }}
              value={runcodeName ?? { label: '', value: '' }}
              tid={Number(data.data.tid)}
              listCustomStyle={{ maxHeight: '170px', overflow: 'auto' }}
              isCloseBorder={false}
            />
          </InputBoxWithLabel>
        </div>

        {modalType === 'CREATE_JOB' && (
          <div className={cx('row')}>
            {trainingType === 'built-in' ? (
              <ParameterInput
                label='parameters.label'
                multiValues={parameterValues}
                onChange={onChangeBuiltInParameter}
                onAdd={onAdd}
                name='params'
                onRemove={onRemove}
                error={parameterError}
              />
            ) : (
              <MultiText
                label='parameters.label'
                multiValues={parameterValues}
                onChange={onChangeParameter}
                onAdd={onAdd}
                name='params'
                placeholder={'파라미터를 입력하세요.'}
                onRemove={onRemove}
                error={parameterError}
                isSampleShow={true}
              />
            )}
          </div>
        )}
      </div>
    </NewStyleModalFrame>
  );
};

export default withTranslation()(JobCreateFormModal);
