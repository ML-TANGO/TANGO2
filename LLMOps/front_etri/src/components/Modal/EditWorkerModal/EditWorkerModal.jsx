// i18n
import {
  InputNumber,
  InputText,
  Radio as TangoRadio,
  Selectbox,
  Textarea,
} from '@tango/ui-react';

// 아이콘 이미지
import builtInImage from '@src/static/images/icon/ic-builtIn-gray.svg';
import trainingImage from '@src/static/images/icon/icon-trainings-gray.svg';
import { useTranslation } from 'react-i18next';

import Radio from '@src/components/atoms/input/Radio';
import GpuNodeSelectBox from '@src/components/molecules/GpuNodeSelectBox';
import GpuSelectBox from '@src/components/molecules/GpuSelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';
import DeploymentType from '@src/components/organisms/DeploymentType';
import BuiltInType from '@src/components/organisms/DeploymentType/BuiltInType';
import TrainingType from '@src/components/organisms/DeploymentType/TrainingType';
import CpuModelSelectBox from '@src/components/organisms/ResourceSettingBox/CpuModelSelectBox';
import GpuModelSelectBox from '@src/components/organisms/ResourceSettingBox/GpuModelSelectBox';

// Components
import ModalFrame from '../ModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './EditWorkerModal.module.scss';

const cx = classNames.bind(style);

const IS_HIDE_SPECIFIC_GPU_MODEL =
  import.meta.env.VITE_REACT_APP_IS_HIDE_SPECIFIC_GPU_MODEL === 'true';
const IS_HIDE_SPECIFIC_CPU_MODEL =
  import.meta.env.VITE_REACT_APP_IS_HIDE_SPECIFIC_CPU_MODEL === 'true';

const EditWorkerModal = ({
  validate,
  data,
  type,
  deploymentName, // 배포 이름
  deploymentNameError, // 배포 이름 에러 텍스트
  deploymentDesc, // 배포 설명 텍스트
  deploymentDescError, // 배포 설명 에러 텍스트
  workspaceOptions, // 워크스페이스 옵션
  workspace,
  deploymentType, // 선택된 배포 타입
  radioBtnHandler, // 배포 타입 라디오 버튼 이벤트 핸들러
  instanceType, // 인스턴스 타입
  gpuModelType, // 선택된 gpu model 타입
  gpuModelListOptions, // gpu model 리스트 옵션
  selectGpuModelHandler, // gpu model 리스트 핸들러
  dockerImageOptions, // Docker Image 옵션
  dockerImage, // 선택된 Docker Image
  textInputHandler, // 텍스트 인풋 이벤트 핸들러
  numberInputHandler, // 넘버 인풋 이벤트 핸들러
  selectInputHandler, // 셀렉트 인풋 이벤트 핸들러
  prevGpuCount, // 이전에 선택했었던 gpu value 값
  gpuUsage, // gpu usage
  gpuTotal, // 총 gpu 갯수
  gpuFree, // gpu usage 사용가능한 최대 갯수
  gpuUsageError, // gpu usage 에러 텍스트
  accessTypeOptions, // access type 옵션
  accessType, // 선택된 access type
  ownerOptions, // owner 셀렉트 옵션
  owner, // 선택된 owner
  multiSelectHandler, // 멀티 셀렉트 이벤트 핸들러
  userList,
  selectedList,
  permissionLevel,
  dockerImageSelectedItemIdx,
  modelTypeHandler,
  modelType,
  gpuTotalValue,
  gpuRamTotalValue,
  gpuDetailValue,
  gpuRamDetailValue,
  gpuTotalSliderMove,
  gpuSwitchStatus,
  gpuAndRamSliderValue,
  gpuDetailSelectedOptions,
  gpuSelectedOptions,
  cpuModelStatus,
  cpuSliderMove,
  cpuSwitchStatus,
  cpuSelectedOptions,
  detailSelectedOptions,
  cpuTotalValue,
  ramTotalValue,
  cpuDetailValue,
  ramDetailValue,
  cpuAndRamSliderValue,
  submitBtnHandler,
  prevSliderData,
  sliderIsValidate,
  totalValueHandler,
  totalSliderHandler,
  sliderSwitchHandler,
  cpuModelTypeHandler,
  gpuModelTypeHandler,
  detailCpuValueHandler,
  detailGpuValueHandler,
  checkboxHandler,
  cpuModelType,
  onChangeGpuInputValue,
  deploymentTypeHandler,
  trainingList,
  selectedDeploymentType,
  trainingSelectedType,
  trainingSelectedOwner,
  trainingTypeSelectHandler,
  trainingSearch,
  trainingInputValue,
  trainingSortHandler,
  backBtnHandler,
  tabClickHandler,
  getJobList,
  getJobs,
  jobDetailList,
  toolDetailOpenHandler,
  jobList,
  jobDetailOpenList,
  hpsList,
  hpsDetailList,
  hpsDetailOpenList,
  trainingToolTab,
  trainingToolTabHandler,
  selectedTool,
  selectedToolType,
  selectedTraining,
  toolSelectHandler,
  trainingSelectHandler,
  paramsInputHandler,
  trainingType,
  getCustomList,
  customFile,
  customParam,
  runcodeClickHandler,
  customRuncode,
  variablesAdd,
  variablesDelete,
  variablesValues,
  variableInputHandler,
  customList,
  variablesSortHandler,
  customSearchValue,
  hpsLogTable,
  selectedHpsScore,
  selectedHps,
  customLan,
  onSubmit,
  templateData,
  makeNewGroup,
  clickedDataList, // 배포유형 -> 템플릿 사용하기 -> 선택 된 그룹
  clickedTemplateLists, // 배포유형 -> 템플릿 사용하기 -> 선택 된 템플릿
  groupSelect,
  onClickGroupSelect,
  onClickTemplateList,
  onClickGroupList,
  setClickedDataList,
  setMakeNewGroup,
  getTemplateListHandler,
  onClickNewGroup,
  groupNameInputHandler,
  newGroupName,
  newGroupDescription,
  groupNameError,
  groupDescriptionInputHandler,
  templateNewNameInputHandler,
  templateNewDescriptionInputHandler,
  templateNewName,
  templateNewDescription,
  templateNameError,
  applyButtonClicked,
  templateOpenStatus,
  onClickTemplateBox,
  customListStatus,
  toolSortHandler,
  toolSearchValue,
  toolSelectedOwner,
  toolModelSearchValue,
  hpsLogSortHandler,
  selectedTrainingData,
  selectedHpsId,
  selectedLogId,
  logClickHandler,
  toolModelSortHandler,
  hpsModelList,
  jobModelList,
  hpsModelSelectValue,
  jobModelSelectValue,
  toolModelSelectHandler,
  trainingTypeArrow,
  trainingTypeArrowHandler,
  builtInModelsList,
  searchModelHandler,
  modelCategorySelect,
  categoryHandler,
  modelList,
  onClickModelList,
  modelSelectStatus,
  modelSelectStatusHanlder,
  selectedModel,
  jsonDataHandler,
  jsonData,
  isMigModel,
  // gpuTotalCount,
  showSelectAgain,
  defaultGroupName,
  defaultTemplateName,
  groupData,
  jsonRef,
  gpuModelList,
  gpuModel,
  gpuList,
  gpuInputValues,
  onClickNoGroup,
  deploymentNoGroupSelected,
  readOnly,
  editStatus,
  isFirstWorkerSetup,
  jsonDataErrorHandler,
  workerSettingType,
  resetCustomInputAndEnvironments,
  gpuAllocate,
  gpuMaxTotal,
  onChangeWorkerGpuInputValue,
  gpuModelName,
  gpuClusterList,
  gpuClusterOption,
  gpuClusterSelectedOption,
  handleGpuClusterOption,
  handleSelectedGpuCluster,
  footerMessage,
  distributionLearningOption,
  distributionLearningSelectedOption,
  handleDistributionLearningOption,
  selectedGpuClusterType,
  gpuClusterType,
  handleGpuClusterType,
  distributionConfigFile,
  selectedDistributionConfigFile,
  handleSelectedDistributionConfigFile,
}) => {
  const { t } = useTranslation();
  const { submit, cancel, workspaceId } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={
        type === 'EDIT_WORKER'
          ? t('createDeploymentForm.title.label')
          : t('editDeploymentForm.title.label')
      }
      footerMessage={footerMessage}
    >
      <h2 className={cx('title')}>
        {/* {type === 'EDIT_WORKER'
          ? t('createDeploymentForm.title.label')
          : t('editDeploymentForm.title.label')} */}
        {t('settingWorker.label')}
      </h2>
      <div className={cx('form')}>
        {/* * 초기 워커 설정일때 보여주는것이다 */}
        {!workerSettingType && (
          <>
            <p className={cx('input-group-title')}>
              {t('basicInformationSettings.title.label')}
            </p>
            {/* <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('deploymentName.label')}
                labelSize='large'
                errorMsg={t(deploymentNameError)}
              >
                <InputText
                  size='large'
                  placeholder={t('deploymentName.placeholder')}
                  name='deploymentName'
                  value={deploymentName}
                  onChange={textInputHandler}
                  status={deploymentNameError ? 'error' : 'default'}
                  isReadOnly={true}
                  disableLeftIcon
                  disableClearBtn
                  isLowercase
                  options={{ maxLength: 50 }}
                  autoFocus={true}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('deploymentDescription.label')}
                optionalText={t('optional.label')}
                labelSize='large'
                optionalSize='large'
                errorMsg={t(deploymentDescError)}
              >
                <Textarea
                  size='large'
                  placeholder={t('deploymentDescription.placeholder')}
                  value={deploymentDesc}
                  name='deploymentDesc'
                  onChange={textInputHandler}
                  maxLength={1000}
                  isShowMaxLength
                  status={
                    deploymentDescError === null
                      ? ''
                      : deploymentDescError === ''
                      ? 'success'
                      : 'error'
                  }
                />
              </InputBoxWithLabel>
            </div> */}
            {/* <p
              className={cx('input-group-title')}
              style={{ marginTop: '36px' }}
            >
              {t('deploymentSettings.title.label')}
            </p> */}
          </>
        )}
        {/* {<div className={cx('title-label')}>{t('deploymentType.label')}</div>} */}
        {/** 도커 이미지 선택하는 파트 */}
        {
          <div>
            <InputBoxWithLabel
              labelText={t('dockerImage.label')}
              labelSize='large'
            >
              <Selectbox
                size='large'
                list={dockerImageOptions}
                selectedItem={dockerImage}
                newSelectedItem={dockerImage}
                newSelectedItemF
                initState={(() => {
                  if (deploymentType === 'built-in') {
                    return false;
                  }
                  return dockerImageSelectedItemIdx === null ? true : false;
                })()}
                placeholder={t('dockerImage.placeholder')}
                type='search'
                onChange={(value) => {
                  selectInputHandler('dockerImage', value);
                }}
                isReadOnly={deploymentType === 'built-in'}
                customStyle={{
                  fontStyle: {
                    selectbox: {
                      fontSize: '14px',
                      fontFamily: 'SpoqaM',
                      color: '#121619',
                      textShadow: 'None',
                    },
                    list: {
                      fontSize: '14px',
                      color: '#121619',
                    },
                  },
                }}
              />
            </InputBoxWithLabel>
          </div>
        }
        {/* 학습 모델 & 체크 포인트 START */}
        {
          <DeploymentType
            type={type}
            deploymentTypeHandler={deploymentTypeHandler}
            selectedDeploymentType={selectedDeploymentType}
            trainingList={trainingList}
            trainingSelectedType={trainingSelectedType}
            trainingSelectedOwner={trainingSelectedOwner}
            trainingTypeSelectHandler={trainingTypeSelectHandler}
            trainingSearch={trainingSearch}
            trainingSortHandler={trainingSortHandler}
            trainingInputValue={trainingInputValue}
            backBtnHandler={backBtnHandler}
            getJobList={getJobList}
            tabClickHandler={tabClickHandler}
            getJobs={getJobs}
            jobDetailList={jobDetailList}
            toolDetailOpenHandler={toolDetailOpenHandler}
            jobList={jobList}
            jobDetailOpenList={jobDetailOpenList}
            trainingToolTab={trainingToolTab}
            trainingToolTabHandler={trainingToolTabHandler}
            hpsList={hpsList}
            hpsDetailList={hpsDetailList}
            hpsDetailOpenList={hpsDetailOpenList}
            selectedTool={selectedTool}
            selectedToolType={selectedToolType}
            toolSelectHandler={toolSelectHandler}
            trainingSelectHandler={trainingSelectHandler}
            selectedTraining={selectedTraining}
            trainingType={trainingType}
            getCustomList={getCustomList}
            paramsInputHandler={paramsInputHandler}
            customFile={customFile}
            customParam={customParam}
            customRuncode={customRuncode}
            variablesAdd={variablesAdd}
            variablesDelete={variablesDelete}
            variablesValues={variablesValues}
            runcodeClickHandler={runcodeClickHandler}
            variablesSortHandler={variablesSortHandler}
            variableInputHandler={variableInputHandler}
            customSearchValue={customSearchValue}
            customList={customList}
            customListStatus={customListStatus}
            hpsLogTable={hpsLogTable}
            customLan={customLan}
            selectedHpsScore={selectedHpsScore}
            selectedHps={selectedHps}
            groupData={groupData}
            workspaceId={workspaceId}
            componentType={'deployment'}
            templateData={templateData}
            makeNewGroup={makeNewGroup}
            clickedDataList={clickedDataList}
            clickedTemplateLists={clickedTemplateLists}
            groupSelect={groupSelect}
            onClickGroupSelect={onClickGroupSelect}
            onClickTemplateList={onClickTemplateList}
            onClickGroupList={onClickGroupList}
            setClickedDataList={setClickedDataList}
            setMakeNewGroup={setMakeNewGroup}
            getTemplateListHandler={getTemplateListHandler}
            onClickNewGroup={onClickNewGroup}
            groupNameInputHandler={groupNameInputHandler}
            newGroupName={newGroupName}
            newGroupDescription={newGroupDescription}
            groupNameDuplicate={groupNameError}
            groupDescriptionInputHandler={groupDescriptionInputHandler}
            templateNewNameInputHandler={templateNewNameInputHandler}
            templateNewDescriptionInputHandler={
              templateNewDescriptionInputHandler
            }
            templateNewName={templateNewName}
            templateNewDescription={templateNewDescription}
            templateNameDuplicate={templateNameError}
            applyButtonClicked={applyButtonClicked}
            defaultGroupName={defaultGroupName}
            defaultTemplateName={defaultTemplateName}
            toolSortHandler={toolSortHandler}
            toolSearchValue={toolSearchValue}
            toolSelectedOwner={toolSelectedOwner}
            templateOpenStatus={templateOpenStatus}
            onClickTemplateBox={onClickTemplateBox}
            hpsLogSortHandler={hpsLogSortHandler}
            selectedHpsId={selectedHpsId}
            selectedLogId={selectedLogId}
            logClickHandler={logClickHandler}
            selectedTrainingData={selectedTrainingData}
            toolModelSearchValue={toolModelSearchValue}
            toolModelSortHandler={toolModelSortHandler}
            hpsModelList={hpsModelList}
            jobModelList={jobModelList}
            hpsModelSelectValue={hpsModelSelectValue}
            jobModelSelectValue={jobModelSelectValue}
            toolModelSelectHandler={toolModelSelectHandler}
            trainingTypeArrow={trainingTypeArrow}
            trainingTypeArrowHandler={trainingTypeArrowHandler}
            builtInModelsList={builtInModelsList}
            modelList={modelList}
            searchModelHandler={searchModelHandler}
            modelCategorySelect={modelCategorySelect}
            categoryHandler={categoryHandler}
            onClickModelList={onClickModelList}
            modelSelectStatus={modelSelectStatus}
            modelSelectStatusHanlder={modelSelectStatusHanlder}
            selectedModel={selectedModel}
            jsonDataHandler={jsonDataHandler}
            jsonData={jsonData}
            showSelectAgain={showSelectAgain}
            jsonDataErrorHandler={jsonDataErrorHandler}
            innerRef={jsonRef}
            onClickNoGroup={onClickNoGroup}
            deploymentNoGroupSelected={deploymentNoGroupSelected}
            workerSettingType={workerSettingType}
            resetCustomInputAndEnvironments={resetCustomInputAndEnvironments}
            t={t}
          />
        }

        {!workspaceId && (
          <div className={cx('row')}>
            <InputBoxWithLabel
              labelText={t('workspace.label')}
              labelSize='large'
            >
              <Selectbox
                isReadOnly={type === 'EDIT_WORKER'}
                size='large'
                list={workspaceOptions}
                selectedItem={workspace}
                placeholder={t('workspace.placeholder')}
                onChange={(value) => {
                  selectInputHandler('workspace', value);
                }}
                scrollAutoFocus={true}
              />
            </InputBoxWithLabel>
          </div>
        )}

        {/* 학습 모델 & 체크 포인트 END */}
        <div className={cx('row')}>
          {/** 기존 cpu gpu 선택하는 라디오 버튼 삭제 */}
          {/* <InputBoxWithLabel
            labelText={t('resourceType.label')}
            labelSize='large'
          >
            <Radio
              label='resourceType.label'
              options={[
                {
                  label: 'gpuModel.label',
                  value: 0,
                },
                { label: 'cpuModel.label', value: 1 },
              ]}
              name='modelTypeOptions'
              value={modelType}
              onChange={(e) => {
                modelTypeHandler(
                  Number(e.target.value),
                  selectedModel?.deployment_multi_gpu_mode,
                );
              }}
              customStyle={{ marginTop: '15px' }}
              readOnly={
                selectedModel &&
                selectedModel.deployment_type === 'built-in' &&
                (!selectedModel?.enable_to_deploy_with_cpu ||
                  !selectedModel?.enable_to_deploy_with_gpu)
              }
            />
          </InputBoxWithLabel> */}

          {/** 워커 별 GPU 할당  */}
          {gpuModelName !== 'CPU 인스턴스 입니다.' && gpuModelName !== '' ? (
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={`${t(
                  instanceType === 'NPU'
                    ? 'npuAllocationReq.label'
                    : 'gpuAllocationReq.label',
                )}`}
                labelSize='large'
                labelDescText={gpuModelName}
                labelDescStyle={{
                  fontSize: '12px',
                  color: '#747474',
                  marginLeft: '8px',
                  transform: 'translateY(-2px)',
                }}
              >
                <InputNumber
                  name='gpuInput'
                  placeholder={`${t('currentAvailableCount')} : ${gpuMaxTotal}`}
                  min={0}
                  max={gpuMaxTotal}
                  value={gpuAllocate}
                  onChange={(e) => {
                    let inputValue = e.value;

                    onChangeWorkerGpuInputValue(inputValue);
                  }}
                />
              </InputBoxWithLabel>
            </div>
          ) : (
            ''
          )}

          {/** 분산 학습 백엔드 */}
          {/* {gpuAllocate > 1 && (
            <div className={cx('radio-wrap')}>
              <label className={cx('label')}>
                {t('distributedLearningBackend.label')}
                <div className={cx('label-right-item')}></div>
              </label>
              <TangoRadio
                options={distributionLearningOption}
                onChange={(e) => {
                  handleDistributionLearningOption(e.currentTarget.value);
                }}
                selectedValue={distributionLearningSelectedOption}
                name='learning'
                t={t}
              />
              <div className={cx('cluster-info')}>
                <div>
                  {distributionLearningSelectedOption === 1 && (
                    <span className={cx('warning')}>
                      {t('workerNccl.warning')}
                    </span>
                  )}
                  {distributionLearningSelectedOption === 2 && (
                    <span className={cx('warning')}>
                      {t('workerMpi.warning')}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )} */}

          {/** 분산추론 호스트 설정 파일 선택 */}
          {/* {gpuAllocate > 1 && (
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('workerHostOptionFile.label')}
                labelSize='large'
              >
                <Selectbox
                  size='large'
                  placeholder={t('workerHostOptionFile.placeholder')}
                  list={distributionConfigFile}
                  selectedItem={selectedDistributionConfigFile}
                  onChange={(v) => {
                    handleSelectedDistributionConfigFile(v);
                  }}
                  customStyle={{
                    fontStyle: {
                      selectbox: {
                        color: '#121619',
                        textShadow: 'None',
                      },
                    },
                  }}
                />
              </InputBoxWithLabel>
            </div>
          )} */}

          {/** GPU 클러스터 설정 유형 안보여주도록 주석처리 */}
          {gpuAllocate > 1 && (
            <div className={cx('gpu-container')}>
              <div className={cx('radio-wrap')}>
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
                    onChange={(e) => {
                      handleGpuClusterOption(e.currentTarget.value);
                    }}
                    value={gpuClusterSelectedOption}
                    isShowAllDesc={false}
                    isLabelColor={true}
                  />
                </InputBoxWithLabel>
              </div>

              {gpuClusterType.length ? (
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
                      onChange={(e) => {
                        handleGpuClusterType(e.currentTarget.value);
                      }}
                      value={selectedGpuClusterType}
                    />
                  </InputBoxWithLabel>
                </div>
              ) : (
                ''
              )}
            </div>
          )}

          {/** GPU 클러스터 선택 리스트 GPU 할당 2개 이상일때 보여줘야한다. 그리고 GPU 클러스터 설정이 수동일때 보여줘야한다. */}
          {/* {gpuAllocate > 1 && gpuClusterSelectedOption === 0 && (
            <div className={cx('row')}>
              <GpuNodeSelectBox
                gpuClusterList={gpuClusterList}
                handleSelectedGpuCluster={handleSelectedGpuCluster}
              />
            </div>
          )} */}

          {/** 기존  워커 자원 설정 GPU 할당 요청 */}
          {/* <div className={cx('input-group')}>
            <>
              <div className={cx('group-title')}>
                <span className={cx('text')}>
                  {t('deploymentsOption.label')}
                </span>
              </div>
              {t('gpuAllocationReq.label')}
              <GpuSelectBox
                models={gpuModel}
                checkboxHandler={checkboxHandler}
                gpuSelectedOptions={gpuSelectedOptions}
                onChangeGpuInputValue={onChangeGpuInputValue}
                prevGpuCount={prevGpuCount}
                inputValue={gpuInputValues}
                edit={type === 'EDIT_WORKER'}
                type={type}
              />
            </>
          </div> */}

          {/* {modelType === 0 && !IS_HIDE_SPECIFIC_GPU_MODEL && (
            <InputBoxWithLabel
              labelText={t('gpuModel.label')}
              labelSize='large'
              disableErrorMsg={gpuModelType === 1}
            >
              <Radio
                options={[
                  {
                    label: 'random.label',
                    value: 0,
                  },
                  { label: 'specificModel.label', value: 1 },
                ]}
                label={'gpuModel.label'}
                name='gpuModelType'
                value={gpuModelType}
                onChange={(e) => {
                  gpuModelTypeHandler(e.target.value);
                  radioBtnHandler(e);
                }}
              />
            </InputBoxWithLabel>
          )}
          {modelType === 1 && !IS_HIDE_SPECIFIC_CPU_MODEL && (
            <InputBoxWithLabel
              labelText={t('cpuModel.label')}
              labelSize='large'
              disableErrorMsg={cpuModelType === 1}
            >
              <Radio
                options={[
                  {
                    label: 'random.label',
                    value: 0,
                  },
                  { label: 'specificModel.label', value: 1 },
                ]}
                name='cpuModelType'
                value={cpuModelType}
                onChange={(e) => {
                  cpuModelTypeHandler(e.target.value);
                }}
              />
            </InputBoxWithLabel>
          )} */}
        </div>
        {modelType === 1 && cpuModelType === 1 && (
          <div className={cx('row')}>
            <CpuModelSelectBox
              options={cpuModelStatus}
              cpuSelectedOptions={cpuSelectedOptions}
              detailSelectedOptions={detailSelectedOptions}
              cpuTotalValue={cpuTotalValue}
              ramTotalValue={ramTotalValue}
              cpuDetailValue={cpuDetailValue}
              ramDetailValue={ramDetailValue}
              cpuAndRamSliderValue={cpuAndRamSliderValue}
              submitBtnHandler={submitBtnHandler}
              checkboxHandler={checkboxHandler}
              detailCpuValueHandler={detailCpuValueHandler}
              totalValueHandler={totalValueHandler}
              totalSliderHandler={totalSliderHandler}
              sliderSwitchHandler={sliderSwitchHandler}
              cpuSliderMove={cpuSliderMove}
              cpuSwitchStatus={cpuSwitchStatus}
              prevSliderData={prevSliderData}
            />
          </div>
        )}
        {/** 접근 권한 */}
        {/* <p className={cx('input-group-title')} style={{ marginTop: '24px' }}>
          {t('accessSettings.title.label')}
        </p> */}
        {/* <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('accessType.label')}
            labelSize='large'
          >
            <Radio
              name='accessType'
              options={accessTypeOptions}
              value={accessType}
              onChange={radioBtnHandler}
              readOnly={permissionLevel > 3 && type === 'EDIT_WORKER'}
            />
          </InputBoxWithLabel>
        </div> */}
        {/* <div className={cx('row')}>
          <InputBoxWithLabel labelText={t('owner.label')} labelSize='large'>
            <Selectbox
              size='large'
              list={ownerOptions}
              selectedItem={owner}
              newSelectedItem={owner}
              newSelectedItemF
              placeholder={t('owner.placeholder')}
              type='search'
              onChange={(value) => {
                selectInputHandler('owner', value);
              }}
              isReadOnly={permissionLevel > 3 && type === 'EDIT_WORKER'}
              customStyle={{
                fontStyle: {
                  selectbox: {
                    fontSize: '16px',
                    fontFamily: 'SpoqaM',
                    color: '#121619',
                    textShadow: 'None',
                  },
                  list: {
                    fontSize: '16px',
                  },
                },
              }}
              scrollAutoFocus={true}
            />
          </InputBoxWithLabel>
        </div> */}
        {/* {accessType === 0 && (
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
              readOnly={permissionLevel > 3 && type === 'EDIT_WORKER'}
            />
          </div>
        )} */}
        <div className={cx('worker-message')}>*{t('workerApply.message')}</div>
      </div>
    </ModalFrame>
  );
};

export default EditWorkerModal;
