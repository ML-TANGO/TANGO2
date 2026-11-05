// Components
import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import { InputText, Selectbox, Textarea, Tooltip } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import HuggingFaceSearch from '@src/components/molecules/HuggingFaceSearch';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import JonathanModelSearch from '@src/components/molecules/JonathanModelSearch';
import MultiSelect from '@src/components/molecules/MultiSelect';
import ResourceSetting from '@src/components/molecules/ResourceSetting';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './TrainingFormModal.module.scss';

const cx = classNames.bind(style);

function TrainingFormModal({
  validate,
  data,
  type,
  trainingType, // 선택된 프로젝트 타입 (training, training jupyter, service)
  trainingTypeOptions, // 프로젝트 타입 선택 옵션
  radioBtnHandler, // 프로젝트 타입 라디오 버튼 이벤트 핸들러
  trainingName, // 프로젝트 이름
  trainingNameError, // 프로젝트 이름 에러 텍스트
  trainingDesc, // 프로젝트 설명 텍스트
  trainingDescError, // 프로젝트 설명 에러 텍스트
  textInputHandler, // 텍스트 인풋 이벤트 핸들러
  numberInputHandler, // 넘버 인풋 이벤트 핸들러
  workspace, // 선택된 워크스페이스
  workspaceOptions, // 워크스페이스 옵션
  selectInputHandler, // 셀렉트 인풋 이벤트 핸들러
  gpuUsage, // gpu usage
  maxGpuUsageCountForRandom, // gpu usage 사용가능한 최대 갯수 (랜덤)
  gpuTotalCountForRandom, // gpu 총 갯수 (랜덤)
  maxGpuUsageCount, // gpu usage 사용가능한 최대 갯수
  minGpuUsage, // gpu usage 사용해야할 최소 갯수
  maxGpuUsage, // 반드시 넘으면 안되는 최대 GPU 수
  gpuTotalCount, // gpu 총 갯수
  isGuranteedGpu, // gpu 보장 여부
  gpuUsageError, // gpu usage 에러 텍스트
  dockerImageOptions, // docker Image 옵션
  dockerImage, // 선택된 docker Image
  instanceModels,
  gpuInputValues,
  gpuModelTypeOptions, // gpu model 타입 옵션
  gpuModelType, // 선택된 gpu model 타입
  cpuModelType, // 선택된 cpu model 타입
  gpuModelListOptions, // gpu model 리스트 옵션
  gpuModelList, // 선택된 gpu model 리 스트
  cpuModelList, // 선택된 cpu model 리스트
  cpuModelInfo,
  isMigModel, // 선택된 gpu model에 MIG 모델 포함 여부
  modelTypeValue,
  handleModelTypeValue,
  selectGpuModelHandler, // gpu model 리스트 핸들러
  accessTypeOptions, // access type 옵션
  accessType, // 선택된 access type
  ownerOptions, // owner 셀렉트 옵션
  owner, // 선택된 owner
  builtInFilterOptions,
  builtInFilter,
  builtInModel,
  builtInModelOptions,
  selectBuiltInModelHandler,
  multiSelectHandler, // 멀티 셀렉트 이벤트 핸들러
  trainingStatus,
  userList,
  selectedList,
  thumbnailList,
  onSubmit,
  permissionLevel,
  builtInModelSearchResult,
  onBuiltInModelSearch,
  modelTypeOptions,
  resourceTypeReadOnly,
  modelType,
  cpuModelTypeOptions,
  modelRadioBtnHandler,
  // ---- slider 관련 props ----
  //  gpu
  gpuSliderSwitch,
  gpuSelectedOptions,
  gpuDetailSelectedOptions,
  gpuTotalValue,
  gpuRamTotalValue,
  gpuDetailValue,
  gpuRamDetailValue,
  gpuTotalSliderMove,
  gpuSwitchStatus,
  gpuAndRamSliderValue,
  // cpu
  cpuSelectedOptions,
  detailSelectedOptions,
  cpuTotalValue,
  ramTotalValue,
  cpuDetailValue,
  ramDetailValue,
  cpuSliderMove,
  cpuSwitchStatus,
  cpuAndRamSliderValue,
  // slider func
  checkboxHandler,
  detailCpuValueHandler,
  detailGpuValueHandler,
  totalValueHandler,
  totalSliderHandler,
  sliderSwitchHandler,
  onChangeGpuInputValue,
  // 추가 타입
  selectedCategory,
  selectedModel,
  handleCategoryValue,
  handleModelValue,

  huggingFaceToken,
  selectedHuggingFaceModel,
  handleHuggingFaceValue,
  handleHuggingFaceToken,
  // footerMessage
  footerMessage,
  ...rest
}) {
  const [event, setEvent] = useState(false);
  const { t } = useTranslation();
  const { submit, cancel, workspaceId } = data;

  const col1 = t('instanceName.label');

  const col2 = (
    <>
      <div>{t('totalAmount.label')}</div>
    </>
  );

  const col3 = (
    <>
      <div>{t('allocation.label')}</div>
    </>
  );

  const colList = [col1, col2, col3];

  const newSubmit = {
    text: submit.text,
    func: async () => {
      setEvent(true);
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const title =
    type === 'CREATE_TRAINING'
      ? t('createTrainingForm.title.label')
      : t('editTrainingForm.title.label');

  const newInstanceModels = instanceModels.map((el) => {
    const first_name = el.name.split('.')[0];
    return {
      ...el,
      gpu_name: first_name !== 'CPU' && first_name,
    };
  });

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate && !footerMessage}
      isResize={true}
      isMinimize={true}
      title={title}
      headerTitle={title}
      submitBtnTestId='create-training-btn'
      footerMessage={footerMessage}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('trainingName.label')}
            labelSize='large'
            disableErrorMsg
          >
            <InputText
              size='medium'
              placeholder={t('trainingName.placeholder')}
              name='trainingName'
              value={trainingName}
              onChange={textInputHandler}
              onClear={() =>
                textInputHandler({
                  target: { name: 'trainingName', value: '' },
                })
              }
              status={trainingNameError ? 'error' : 'default'}
              isReadOnly={type === 'EDIT_TRAINING'}
              isLowercase
              options={{ maxLength: 20 }}
              autoFocus
              disableLeftIcon
              disableClearBtn={false}
              testId='training-name-input'
              customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('trainingDescription.label')}
            optionalText={t('optional.label')}
            labelSize='large'
            optionalSize='medium'
            disableErrorMsg
          >
            <Textarea
              size='large'
              placeholder={t('trainingDescription.placeholder')}
              value={trainingDesc}
              name='trainingDesc'
              onChange={textInputHandler}
              maxLength={1000}
              isShowMaxLength
              testId='training-desc-input'
              status={
                trainingDescError === null
                  ? ''
                  : trainingDescError === ''
                  ? 'success'
                  : 'error'
              }
              isReadOnly={permissionLevel < 2 && type === 'EDIT_TRAINING'}
              customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
            />
          </InputBoxWithLabel>
        </div>
        {!workspaceId && (
          <div className={cx('row')}>
            <InputBoxWithLabel
              labelText={t('workspace.label')}
              labelSize='large'
            >
              <Selectbox
                type='search'
                size='large'
                list={workspaceOptions}
                placeholder={t('workspace.placeholder')}
                selectedItem={workspace}
                onChange={(value) => {
                  selectInputHandler('workspace', value);
                }}
                isReadOnly={type === 'EDIT_TRAINING'}
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
            </InputBoxWithLabel>
          </div>
        )}

        {/* ** 학습 자원 설정 ** */}
        {modelType === 0 && (
          <div className={cx('row')}>
            <InputBoxWithLabel
              labelText={t('assignTrainingSetting.label')}
              labelSize='large'
              disableErrorMsg
            >
              <ResourceSetting
                isInstance
                models={newInstanceModels}
                checkboxHandler={checkboxHandler}
                gpuSelectedOptions={gpuSelectedOptions}
                onChangeGpuInputValue={onChangeGpuInputValue}
                inputValue={gpuInputValues}
                edit={type === 'EDIT_TRAININGS'}
                colList={colList}
                type={'gpu'}
              />
            </InputBoxWithLabel>
          </div>
        )}

        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={'모델 유형'}
            labelSize='large'
            disableErrorMsg
            style={{ marginBottom: '32px' }}
          >
            <Radio
              name='modelType'
              value={modelTypeValue}
              options={[
                { label: 'Custom', value: 0 },
                { label: 'Jonathan Intelligence', value: 1 },
                { label: 'Hugging Face', value: 2 },
              ]}
              onChange={handleModelTypeValue}
              readOnly={type === 'EDIT_TRAINING'}
              isLabelColor
            />
          </InputBoxWithLabel>
        </div>
        {modelTypeValue === 1 && (
          <JonathanModelSearch
            selectCategory={selectedCategory}
            setSelectCategory={handleCategoryValue}
            selectModel={selectedModel}
            setSelectModel={handleModelValue}
            style={{ marginBottom: '32px' }}
            disabled={type === 'EDIT_TRAINING'}
          />
        )}
        {modelTypeValue === 2 && (
          <HuggingFaceSearch
            selectCategory={selectedCategory}
            setSelectCategory={handleCategoryValue}
            selectModel={selectedHuggingFaceModel}
            setSelectModel={handleHuggingFaceValue}
            huggingFaceToken={huggingFaceToken}
            handleHuggingFaceToken={handleHuggingFaceToken}
            style={{ marginBottom: '32px' }}
            disabled={type === 'EDIT_TRAINING'}
          />
        )}

        <div className={cx('row')}>
          <div className={cx('flex-cont')}>
            <div className={cx('accessType-cont')}>
              <InputBoxWithLabel
                labelText={t('accessType.label')}
                labelSize='large'
                labelRight={
                  <Tooltip
                    contents={
                      <div className={cx('tooltip-content')}>
                        <p className={cx('tooltip-header')}>
                          {t('trainingAccessType.tooltip.title')}
                        </p>
                        <p>{t('trainingAccessType.tooltip1.message')}</p>
                        <p>{t('trainingAccessType.tooltip2.message')}</p>
                        <p>{t('trainingAccessType.tooltip3.message')}</p>
                      </div>
                    }
                    contentsCustomStyle={{
                      border: '0.5px solid #DEE9FF',
                      borderRadius: '10px',
                      boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                      padding: '20px 24px',
                      width: '320px',
                      zIndex: 1000,
                    }}
                    contentsAlign={{ vertical: 'top' }}
                    iconCustomStyle={{
                      width: '20px',
                      height: '20px',
                      marginLeft: '4px',
                      verticalAlign: 'text-top',
                    }}
                  />
                }
                disableErrorMsg
              >
                <Radio
                  label='accessType.label'
                  name='accessType'
                  options={accessTypeOptions}
                  value={accessType}
                  onChange={(e) => {
                    radioBtnHandler('accessType', e.target.value);
                  }}
                  readOnly={permissionLevel < 2 && type === 'EDIT_TRAINING'}
                  isLabelColor
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('owner-cont')}>
              <InputBoxWithLabel
                labelText={t('owner.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Selectbox
                  type='search'
                  size='medium'
                  list={ownerOptions}
                  placeholder={t('owner.placeholder')}
                  selectedItem={owner}
                  onChange={(value) => {
                    selectInputHandler('owner', value);
                  }}
                  isReadOnly={
                    (permissionLevel < 2 && type === 'EDIT_TRAINING') ||
                    !workspace
                  }
                  customStyle={{
                    fontStyle: {
                      selectbox: {
                        color:
                          (permissionLevel < 2 && type === 'EDIT_TRAINING') ||
                          !workspace
                            ? '#747474'
                            : '#121619',
                        textShadow: 'None',
                        fontSize: '14px',
                      },
                      list: {
                        fontSize: '14px',
                      },
                    },
                  }}
                  scrollAutoFocus={true}
                />
              </InputBoxWithLabel>
            </div>
          </div>
        </div>

        {accessType === 0 && (
          <div className={cx('row')}>
            <MultiSelect
              // innerRef={setRef}
              label='users.label'
              listLabel='availableUsers.label'
              selectedLabel='chosenUsers.label'
              list={userList} // 초기 목록
              selectedList={selectedList} // 초기 선택된 목록
              onChange={multiSelectHandler} // 변경 이벤트
              exceptItem={owner && owner.value} // 목록에서 빠질 아이템
              optional
              readOnly={permissionLevel < 2 && type === 'EDIT_TRAINING'}
            />
          </div>
        )}
      </div>
    </NewStyleModalFrame>
  );
}

export default TrainingFormModal;
