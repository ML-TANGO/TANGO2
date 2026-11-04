import { useState, useRef, useEffect, Fragment } from 'react';

// i18n
import { withTranslation } from 'react-i18next';

// Components
import {
  InputText,
  Textarea,
  Button,
  Switch,
  Tooltip,
  Selectbox,
} from '@jonathan/ui-react';
import Radio from '@src/components/atoms/input/Radio';
import Tab from '@src/components/molecules/Tab';
import CheckboxList from '@src/components/molecules/CheckboxList';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ModalFrame from '@src/components/Modal/ModalFrame';
import TrainingParameterForm from './TrainingParameterForm';
import TrainingInputDataTreeForm from './TrainingInputDataTreeForm';
import DeploymentInputForm from './DeploymentInputForm';
import CommandLineParserForm from './CommandLineParserForm';
import ThumbnailForm from './ThumbnailForm';

// CSS module
import classNames from 'classnames/bind';
import style from './BuiltinModelFormModal.module.scss';
const cx = classNames.bind(style);

const BuiltinModelFormModal = ({
  validate,
  validateTraining,
  validateDeployment,
  data,
  type: modalType,
  inputTypeOptions, // 새로 입력 or 목록에서 선택
  booleanTypeOptions, // True(지원) or false(미지원)
  jsonFileName,
  isEnterJson,
  /** 기본 정보 */
  inputTypeModelType, // 모델 유형 입력 방법
  newModelType, // 새로 입력한 모델 유형
  newModelTypeError,
  modelType, // 목록에서 선택한 모델 유형
  modelTypeError,
  filteredModelTypeOptions, // 모델 유형 선택 옵션
  creator, // 생성자
  creatorOptions, // 생성자 선택 옵션
  otherCreator, // JF 외에 생성자
  otherCreatorError,
  modelName, // 모델 이름
  modelNameError,
  modelDesc, // 모델 설명
  inputTypeModelDirectory, // 모델 저장 폴더 입력 방법
  newModelDirectory, //  새로 입력한 모델 저장 폴더
  newModelDirectoryError,
  modelDirectory, // 목록에서 선택한 모델 저장 폴더
  modelDirectoryOptions, // 모델 저장 폴더 선택 옵션
  modelDirectoryError,
  dockerImage, // 도커이미지 (run_docker_name)
  dockerImageOptions, // 도커이미지 선택 옵션
  dockerImageError,
  thumbnailImage, // 썸네일 이미지 src
  thumbnailPath, // 썸네일 파일 이름
  /** 학습 정보 */
  trainingStatus, // 학습 활성화 여부
  modelAlgorithm, // 모델 알고리즘 이름 (model) ex) RNN LSTM
  trainingDataDesc, // 사용하는 학습 데이터 간단 설명 (train_data)
  trainingInputDataForm, // 학습 데이터 입력 폼 목록
  trainingParameters, // 학습 파라미터
  evaluationIndex, // 평가 지표
  trainingRunCommand, // 학습 실행 기본 명령어
  trainingParserList, // 학습 명령어 파서 목록
  isEnableCpuTraining, // CPU로 학습 가능 여부
  isEnableGpuTraining, // GPU로 학습 가능 여부
  isHorovodTrainingMultiGpu, // Horovod 적용 멀티 GPU 사용 (false 시 GPU 사용 1개 최대)
  isNonhorovodTrainingMultiGpu, // Horovod 미적용 내장 기능으로 멀티 GPU 사용
  isEnableRetraining, // 재학습(이어하기) 가능 여부
  retrainingParserList, // 재학습 명령어 파서 목록
  isMarkerLabeling, // 마커 사용 가능 여부
  isAutoLabeling, // 오토라벨링 사용 가능 여부
  /** 배포 정보 */
  deploymentStatus, // 배포 활성화 여부
  deploymentInputForm, // 배포 입력 폼 목록
  deploymentOutputTypes, // 배포 결과 유형 (text, video, image, audio, barchart, columnchart, piechart, table, obj)
  otherDeploymentOutputTypes, // 배포 결과 유형 (기타 - 직접입력)
  otherDeploymentOutputTypesError,
  deploymentRunCommand, // 배포 실행 기본 명령어
  deploymentParserList, // 배포 명령어 파서 목록
  isExistDefaultCheckpoint, // 미리 학습된 체크포인트 존재 여부
  isEnableCpuDeployment, // CPU로 배포 가능 여부
  isEnableGpuDeployment, // GPU로 배포 가능 여부
  isDeploymentMultiGpu, // 배포 멀티 GPU 사용
  /** 이벤트 핸들러 */
  radioBtnHandler, // 라디오 버튼 이벤트 핸들러
  textInputHandler, // 텍스트 인풋 이벤트 핸들러
  selectInputHandler, // 셀렉트 인풋 이벤트 핸들러
  switchHandler, // 스위치 이벤트 핸들러
  fileInputHandler, // 파일 인풋 이벤트 핸들러(썸네일용)
  removeThumbnail, // 썸네일 삭제(초기화)
  addTrainingInputDataForm, // 학습 데이터 입력 폼 추가
  removeTrainingInputDataForm, // 학습 데이터 입력 폼 삭제
  trainingInputDataFormHandler, // 학습 데이터 입력 이벤트 핸들러
  addTrainingParametersForm, // 학습 파라미터 입력 폼 추가
  trainingParametersFormHandler, // 학습 파라미터 입력 이벤트 핸들러
  removeTrainingParametersForm, // 학습 파라미터 입력 폼 삭제
  addDeploymentInputForm, // 배포 입력값 폼 추가
  removeDeploymentInputForm, // 배포 입력값 폼 삭제
  deploymentInputFormHandler, // 배포 입력값 핸들러
  deploymentOutputTypesHandler, // 배포 결과 유형 체크박스 핸들러
  parserInputHandler, // 파서 입력 핸들러
  onSubmit,
  onReadFile,
  onImportJson,
  t,
}) => {
  const { submit, cancel, prev, next } = data;
  const scrollBoxRef = useRef();
  const fileInput = useRef(null);
  const triggerInputFile = () => fileInput.current.click();

  const targetOptions = [
    { label: t('basicSettings.title.label'), value: 0 },
    { label: t('trainingSettings.title.label'), value: 1 },
    { label: t('deploymentSettings.title.label'), value: 2 },
  ];
  const [target, setTarget] = useState(targetOptions[0]);

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  let newPrev = null;
  let newNext = null;
  if (prev) {
    newPrev = {
      text: prev.text,
      func: () => {
        if (target.value > 0) {
          setTarget(targetOptions[target.value - 1]);
        } else {
          setTarget(targetOptions[0]);
        }
      },
    };
  }
  if (next) {
    newNext = {
      text: next.text,
      func: () => {
        if (target.value < 2) {
          setTarget(targetOptions[target.value + 1]);
        } else {
          setTarget(targetOptions[2]);
        }
      },
    };
  }

  const [hideImportJson, setHideImportJson] = useState(true);
  const [hideTrainingInputDataForm, setHideTrainingInputDataForm] =
    useState(false);
  const [hideTrainingRunCommand, setHideTrainingRunCommand] = useState(false);
  const [hideTrainingParameterForm, setHideTrainingParameterForm] =
    useState(false);
  const [hideDeploymentInputForm, setHideDeploymentInputForm] = useState(false);
  const [hideDeploymentRunCommand, setHideDeploymentRunCommand] =
    useState(false);

  // 스텝 변경시 스크롤 맨위로 이동
  useEffect(() => {
    scrollBoxRef.current.scrollTop = 0;
  }, [target]);

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={modalType}
      validate={
        validate && (target.value === 2 || modalType === 'EDIT_BUILTIN_MODEL')
      }
      prev={newPrev}
      next={newNext}
      nextValidate={validate}
      totalStep={3}
      currentStep={target.value + 1}
      isResize={true}
      isMinimize={true}
      title={
        modalType === 'CREATE_BUILTIN_MODEL'
          ? t('createBuiltinModelForm.title.label')
          : t('editBuiltinModelForm.title.label')
      }
    >
      <h2 className={cx('title')}>
        {modalType === 'CREATE_BUILTIN_MODEL'
          ? t('createBuiltinModelForm.title.label')
          : t('editBuiltinModelForm.title.label')}
        <div
          className={cx(
            'import-box',
            hideImportJson ? 'hide' : 'show',
            jsonFileName && isEnterJson && 'name',
          )}
        >
          <div
            className={cx('title-box')}
            onClick={() => setHideImportJson(!hideImportJson)}
          >
            <label className={cx('import-label')}>
              {t('importJson.label')}{' '}
              <Tooltip
                contents={t('importBuiltinModel.tooltip.message')}
                contentsAlign={{
                  horizontal: hideImportJson ? 'right' : 'left',
                }}
              />
            </label>
            {hideImportJson && isEnterJson && (
              <div className={cx('file-name')} title={jsonFileName}>
                {jsonFileName}
              </div>
            )}
            <button className={cx('show-hide-btn')}>
              <img
                src={`/images/icon/00-ic-basic-arrow-04-${
                  hideImportJson ? 'up' : 'down'
                }.svg`}
                className={cx('arrow-btn')}
                alt='show/hide button'
              />
            </button>
          </div>
          <div className={cx('contents-box')}>
            <div className={cx('file-input-wrap')}>
              <div>
                <input
                  style={{ display: 'none' }}
                  ref={fileInput}
                  type='file'
                  onChange={(e) => {
                    onReadFile(e);
                  }}
                  name='import'
                />
                <button className={cx('btn')} onClick={triggerInputFile}>
                  JSON {t('file.label')}
                </button>
              </div>
              <div className={cx('file-name')} title={jsonFileName}>
                {jsonFileName}
              </div>
            </div>
            <Button
              type='primary'
              size='large'
              onClick={() => {
                onImportJson();
                setHideImportJson(true);
              }}
              disabled={!jsonFileName}
            >
              {t('enter.label')}
            </Button>
          </div>
        </div>
      </h2>
      {modalType === 'EDIT_BUILTIN_MODEL' && (
        <div className={cx('control-box')}>
          <Tab
            type='a'
            option={targetOptions}
            select={target}
            tabHandler={setTarget}
            backgroudColor='#fff'
          >
            <div className={cx('active-box')}>
              <Tooltip
                contents={t('activateBuiltInModel.tooltip.message')}
                contentsAlign={{ horizontal: 'center' }}
              />
              <div className={cx('switch-box', 'training')}>
                <label className={cx('switch-label')}>
                  {t('training.label')}
                </label>
                <Switch
                  name='trainingStatus'
                  onChange={() => switchHandler('training')}
                  checked={trainingStatus && validateTraining}
                  disabled={!validateTraining}
                />
              </div>
              <div className={cx('switch-box', 'deployment')}>
                <label className={cx('switch-label')}>
                  {t('deployment.label')}
                </label>
                <Switch
                  name='deploymentStatus'
                  onChange={() => switchHandler('deployment')}
                  checked={deploymentStatus && validateDeployment}
                  disabled={!validateDeployment}
                />
              </div>
            </div>
          </Tab>
        </div>
      )}
      <div className={cx('form')} ref={scrollBoxRef}>
        {target.value === 0 && (
          <div className={cx('setting-box')}>
            <div className={cx('input-group-title')}>
              {t('basicSettings.title.label')}
            </div>
            {modalType === 'CREATE_BUILTIN_MODEL' && (
              <p className={cx('notice')}>
                {t('createBuiltInModel.tooltip.message')}
              </p>
            )}
            <div className={cx('float-box')}>
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={t('creator.label')}
                  labelSize='large'
                  disableErrorMsg
                >
                  <Radio
                    name='creator'
                    options={creatorOptions}
                    value={creator}
                    onChange={radioBtnHandler}
                  />
                </InputBoxWithLabel>
              </div>
              <div className={cx('column')}>
                <InputText
                  size='large'
                  placeholder={t('creator.placeholder')}
                  name='otherCreator'
                  value={otherCreator}
                  onChange={textInputHandler}
                  isDisabled={creator !== 'other'}
                  customStyle={{ marginTop: '20px' }}
                  disableLeftIcon
                  disableClearBtn
                />
                <div className={cx('error-message')}>
                  {t(otherCreatorError)}
                </div>
              </div>
            </div>
            {modalType === 'CREATE_BUILTIN_MODEL' ? (
              <Fragment>
                <div className={cx('row')}>
                  <InputBoxWithLabel
                    labelText={t('modelType.label')}
                    labelSize='large'
                    disableErrorMsg
                  >
                    <Radio
                      name='inputTypeModelType'
                      options={inputTypeOptions}
                      value={inputTypeModelType}
                      onChange={radioBtnHandler}
                      customStyle={{ marginBottom: '8px' }}
                    />
                  </InputBoxWithLabel>
                </div>
                <div className={cx('row')}>
                  {inputTypeModelType === 0 ? (
                    <>
                      <Selectbox
                        type='search'
                        size='large'
                        list={filteredModelTypeOptions}
                        selectedItem={modelType}
                        placeholder={t('modelType.placeholder')}
                        onChange={(value) => {
                          selectInputHandler('modelType', value);
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
                      <div className={cx('error-message')}>
                        {modelTypeError}
                      </div>
                    </>
                  ) : (
                    <>
                      <InputText
                        size='large'
                        placeholder={t('newModelType.placeholder')}
                        name='newModelType'
                        value={newModelType}
                        onChange={textInputHandler}
                        disableLeftIcon
                        disableClearBtn
                      />
                      <div className={cx('error-message')}>
                        {t(newModelTypeError)}
                      </div>
                    </>
                  )}
                </div>
              </Fragment>
            ) : (
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={t('modelType.label')}
                  labelSize='large'
                  errorMsg={t(newModelTypeError)}
                >
                  <InputText
                    size='large'
                    name='newModelType'
                    value={newModelType}
                    onChange={textInputHandler}
                    disableLeftIcon
                    disableClearBtn
                  />
                </InputBoxWithLabel>
              </div>
            )}
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('modelName.label')}
                labelSize='large'
                errorMsg={t(modelNameError)}
              >
                <InputText
                  size='large'
                  placeholder={t('modelName.placeholder')}
                  name='modelName'
                  value={modelName}
                  onChange={textInputHandler}
                  disableLeftIcon
                  disableClearBtn
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('modelDescription.label')}
                optionalText={t('optional.label')}
                labelSize='large'
                optionalSize='large'
                disableErrorText
              >
                <Textarea
                  size='large'
                  placeholder={t('modelDescription.placeholder')}
                  value={modelDesc}
                  name='modelDesc'
                  onChange={textInputHandler}
                  isShowMaxLength
                />
              </InputBoxWithLabel>
            </div>
            {modalType === 'CREATE_BUILTIN_MODEL' ? (
              <Fragment>
                <div className={cx('row')}>
                  <InputBoxWithLabel
                    labelText={t('modelDirectory.label')}
                    labelSize='large'
                    disableErrorMsg
                  >
                    <Radio
                      label='modelDirectory.label'
                      name='inputTypeModelDirectory'
                      options={inputTypeOptions}
                      value={inputTypeModelDirectory}
                      onChange={radioBtnHandler}
                      customStyle={{ marginBottom: '8px' }}
                    />
                  </InputBoxWithLabel>
                </div>
                <div className={cx('row')}>
                  {inputTypeModelDirectory === 0 ? (
                    <>
                      <Selectbox
                        type='search'
                        size='large'
                        list={modelDirectoryOptions}
                        selectedItem={modelDirectory}
                        placeholder={t('modelDirectory.placeholder')}
                        onChange={(value) => {
                          selectInputHandler('modelDirectory', value);
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
                      <div className={cx('error-message')}>
                        {modelDirectoryError}
                      </div>
                    </>
                  ) : (
                    <>
                      <InputText
                        size='large'
                        placeholder={t('newModelDirectory.placeholder')}
                        name='newModelDirectory'
                        value={newModelDirectory}
                        onChange={textInputHandler}
                        disableLeftIcon
                        disableClearBtn
                      />
                      <div className={cx('error-message')}>
                        {newModelDirectoryError}
                      </div>
                    </>
                  )}
                </div>
              </Fragment>
            ) : (
              <div className={cx('row')}>
                <InputBoxWithLabel
                  labelText={t('modelDirectory.label')}
                  labelSize='large'
                >
                  <InputText
                    size='large'
                    label='modelDirectory.label'
                    name='newModelDirectory'
                    value={newModelDirectory}
                    isReadOnly
                    disableLeftIcon
                    disableClearBtn
                  />
                </InputBoxWithLabel>
              </div>
            )}
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('dockerImage.label')}
                labelSize='large'
                labelRight={
                  <Tooltip
                    contents={t('builtInModelDockerImage.tooltip.message')}
                  />
                }
                errorMsg={t(dockerImageError)}
              >
                <Selectbox
                  size='large'
                  list={dockerImageOptions}
                  selectedItem={dockerImage}
                  placeholder={t('dockerImage.placeholder')}
                  onChange={(value) => {
                    selectInputHandler('dockerImage', value);
                  }}
                  scrollAutoFocus={true}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <label className={cx('label')}>
                {t('thumbnail.label')}{' '}
                <span className={cx('optional')}>- {t('optional.label')}</span>
                <Tooltip
                  contents={
                    <div>
                      <p>{t('thumbnail.tooltip.message')}</p>
                      <p>{t('thumbnail.size.tooltip.message')}</p>
                    </div>
                  }
                  contentsAlign={{ horizontal: 'center' }}
                />
              </label>
              <ThumbnailForm
                thumbnailImage={thumbnailImage}
                thumbnailPath={thumbnailPath}
                onChange={fileInputHandler}
                onRemove={removeThumbnail}
              />
            </div>
          </div>
        )}
        {target.value === 1 && (
          <div className={cx('setting-box')}>
            <div className={cx('input-group-title')}>
              {t('trainingSettings.title.label')}
            </div>
            <label className={cx('label', 'pointer')}>
              {t('trainingInputDataForm.label')}
              <button
                className={cx('show-hide-btn')}
                onClick={() =>
                  setHideTrainingInputDataForm(!hideTrainingInputDataForm)
                }
              >
                <img
                  src={`/images/icon/00-ic-basic-arrow-04-${
                    hideTrainingInputDataForm ? 'up' : 'down'
                  }.svg`}
                  className={cx('arrow-btn')}
                  alt='show/hide button'
                />
              </button>
            </label>
            {hideTrainingInputDataForm && <hr className={cx('hide-line')} />}
            <div
              className={cx(
                'row',
                'template-box',
                hideTrainingInputDataForm ? 'hide' : 'show',
              )}
            >
              <TrainingInputDataTreeForm
                modalType={modalType}
                trainingInputDataForm={trainingInputDataForm}
                addInputForm={addTrainingInputDataForm}
                removeInputForm={removeTrainingInputDataForm}
                inputHandler={trainingInputDataFormHandler}
              />
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('trainingDataDescription.label')}
                optionalText={t('optional.label')}
                labelSize='large'
                optionalSize='large'
                disableErrorText
              >
                <Textarea
                  placeholder={t('trainingDataDescription.placeholder')}
                  name='trainingDataDesc'
                  value={trainingDataDesc}
                  onChange={textInputHandler}
                  isShowMaxLength
                />
              </InputBoxWithLabel>
            </div>
            <label className={cx('label')}>
              {t('trainingRunCommand.label')}
              <button
                className={cx('show-hide-btn')}
                onClick={() =>
                  setHideTrainingRunCommand(!hideTrainingRunCommand)
                }
              >
                <img
                  src={`/images/icon/00-ic-basic-arrow-04-${
                    hideTrainingRunCommand ? 'up' : 'down'
                  }.svg`}
                  className={cx('arrow-btn')}
                  alt='show/hide button'
                />
              </button>
            </label>
            {hideTrainingRunCommand && <hr className={cx('hide-line')} />}
            <div
              className={cx(
                'row',
                'template-box',
                hideTrainingRunCommand ? 'hide' : 'show',
              )}
            >
              <CommandLineParserForm
                commandType='training'
                commandName='trainingRunCommand'
                commandValue={trainingRunCommand}
                parserList={trainingParserList}
                textInputHandler={textInputHandler}
                parserInputHandler={parserInputHandler}
              />
            </div>
            <label className={cx('label', 'pointer')}>
              {t('trainingParameter.label')}{' '}
              <span className={cx('optional')}>- {t('optional.label')}</span>
              <button
                className={cx('show-hide-btn')}
                onClick={() =>
                  setHideTrainingParameterForm(!hideTrainingParameterForm)
                }
              >
                <img
                  src={`/images/icon/00-ic-basic-arrow-04-${
                    hideTrainingParameterForm ? 'up' : 'down'
                  }.svg`}
                  className={cx('arrow-btn')}
                  alt='show/hide button'
                />
              </button>
            </label>
            {hideTrainingParameterForm && <hr className={cx('hide-line')} />}
            <div
              className={cx(
                'row',
                'template-box',
                hideTrainingParameterForm ? 'hide' : 'show',
              )}
            >
              <TrainingParameterForm
                trainingParameters={trainingParameters}
                addInputForm={addTrainingParametersForm}
                removeInputForm={removeTrainingParametersForm}
                inputHandler={trainingParametersFormHandler}
              />
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('modelAlgorithm.label')}
                optionalText={t('optional.label')}
                labelSize='large'
                optionalSize='large'
              >
                <InputText
                  size='large'
                  placeholder='ex) RNN LSTM'
                  name='modelAlgorithm'
                  value={modelAlgorithm}
                  onChange={textInputHandler}
                  disableLeftIcon
                  disableClearBtn
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('evaluationIndex.label')}
                optionalText={t('optional.label')}
                labelSize='large'
                optionalSize='large'
              >
                <InputText
                  size='large'
                  placeholder='ex) Loss'
                  name='evaluationIndex'
                  value={evaluationIndex}
                  onChange={textInputHandler}
                  disableLeftIcon
                  disableClearBtn
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('cpuTraining.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  name='isEnableCpuTraining'
                  options={booleanTypeOptions}
                  value={isEnableCpuTraining}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('gpuTraining.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  name='isEnableGpuTraining'
                  options={booleanTypeOptions}
                  value={isEnableGpuTraining}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('multiGpuWithHorovod.label')}
                labelSize='large'
                labelRight={
                  <Tooltip
                    contents={t('multiGpuWithHorovod.tooltip.message')}
                  />
                }
                disableErrorMsg
              >
                <Radio
                  name='isHorovodTrainingMultiGpu'
                  options={booleanTypeOptions}
                  value={isHorovodTrainingMultiGpu}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('multiGpuWithoutHorovod.label')}
                labelSize='large'
                labelRight={
                  <Tooltip
                    contents={t('multiGpuWithoutHorovod.tooltip.message')}
                  />
                }
                disableErrorMsg
              >
                <Radio
                  label='multiGpuWithoutHorovod.label'
                  name='isNonhorovodTrainingMultiGpu'
                  options={booleanTypeOptions}
                  value={isNonhorovodTrainingMultiGpu}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('retraining.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  name='isEnableRetraining'
                  options={booleanTypeOptions}
                  value={isEnableRetraining}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            {isEnableRetraining === 'true' && (
              <>
                <label className={cx('label')}>
                  {t('retrainingRunCommandParser.label')}
                  <Tooltip
                    contents={t('retrainingRunCommandParser.tooltip.message')}
                    contentsAlign={{ vertical: 'top' }}
                  />
                </label>
                <div className={cx('row', 'template-box')}>
                  <CommandLineParserForm
                    commandType='retraining'
                    parserList={retrainingParserList}
                    textInputHandler={textInputHandler}
                    parserInputHandler={parserInputHandler}
                  />
                </div>
              </>
            )}
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('marker.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  name='isMarkerLabeling'
                  options={booleanTypeOptions}
                  value={isMarkerLabeling}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('autoLabeling.label')}
                labelSize='large'
                labelRight={
                  <Tooltip
                    contents={t('autoLabeling.tooltip.message')}
                    contentsAlign={{ vertical: 'top' }}
                  />
                }
                disableErrorMsg
              >
                <Radio
                  name='isAutoLabeling'
                  options={booleanTypeOptions}
                  value={isAutoLabeling}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
          </div>
        )}
        {target.value === 2 && (
          <div className={cx('setting-box')}>
            <div className={cx('input-group-title')}>
              {t('deploymentSettings.title.label')}
            </div>
            <label className={cx('label', 'pointer')}>
              {t('serviceTestInputForm.label')}
              <button
                className={cx('show-hide-btn')}
                onClick={() =>
                  setHideDeploymentInputForm(!hideDeploymentInputForm)
                }
              >
                <img
                  src={`/images/icon/00-ic-basic-arrow-04-${
                    hideDeploymentInputForm ? 'up' : 'down'
                  }.svg`}
                  className={cx('arrow-btn')}
                  alt='show/hide button'
                />
              </button>
            </label>
            {hideDeploymentInputForm && <hr className={cx('hide-line')} />}
            <div
              className={cx(
                'row',
                'template-box',
                hideDeploymentInputForm ? 'hide' : 'show',
              )}
            >
              <DeploymentInputForm
                deploymentInputForm={deploymentInputForm}
                addInputForm={addDeploymentInputForm}
                removeInputForm={removeDeploymentInputForm}
                inputHandler={deploymentInputFormHandler}
              />
            </div>
            <div className={cx('row')}>
              <CheckboxList
                label='deploymentOutputTypes.label'
                options={deploymentOutputTypes}
                onChange={(_, idx) => deploymentOutputTypesHandler(idx)}
                customStyle={{
                  display: 'flex',
                  flexDirection: 'column',
                }}
                labelRight={
                  <Tooltip
                    contents={t('deploymentOutputTypes.tooltip.message')}
                  />
                }
                disableErrorText
              />
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel errorMsg={t(otherDeploymentOutputTypesError)}>
                <InputText
                  size='medium'
                  placeholder={t('enterOther.placeholder')}
                  name='otherDeploymentOutputTypes'
                  value={otherDeploymentOutputTypes}
                  onChange={textInputHandler}
                  isDisabled={
                    !deploymentOutputTypes[deploymentOutputTypes.length - 1]
                      .checked
                  }
                  disableLeftIcon
                  disableClearBtn
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('defaultCheckpoint.label')}
                labelSize='large'
                labelRight={
                  <Tooltip contents={t('defaultCheckpoint.tooltip.message')} />
                }
                disableErrorMsg
              >
                <Radio
                  name='isExistDefaultCheckpoint'
                  options={[
                    { label: 'exist.label', value: 'true' },
                    { label: 'none.label', value: 'false' },
                  ]}
                  value={isExistDefaultCheckpoint}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <label className={cx('label')}>
              {t('deploymentRunCommand.label')}
              <button
                className={cx('show-hide-btn')}
                onClick={() =>
                  setHideDeploymentRunCommand(!hideDeploymentRunCommand)
                }
              >
                <img
                  src={`/images/icon/00-ic-basic-arrow-04-${
                    hideDeploymentRunCommand ? 'up' : 'down'
                  }.svg`}
                  className={cx('arrow-btn')}
                  alt='show/hide button'
                />
              </button>
            </label>
            {hideDeploymentRunCommand && <hr className={cx('hide-line')} />}
            <div
              className={cx(
                'row',
                'template-box',
                hideDeploymentRunCommand ? 'hide' : 'show',
              )}
            >
              <CommandLineParserForm
                commandType='deployment'
                commandName='deploymentRunCommand'
                commandValue={deploymentRunCommand}
                parserList={deploymentParserList}
                textInputHandler={textInputHandler}
                parserInputHandler={parserInputHandler}
              />
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('cpuDeployment.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  name='isEnableCpuDeployment'
                  options={booleanTypeOptions}
                  value={isEnableCpuDeployment}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('gpuDeployment.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  name='isEnableGpuDeployment'
                  options={booleanTypeOptions}
                  value={isEnableGpuDeployment}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('multiGpuDeployment.label')}
                labelSize='large'
                labelRight={
                  <Tooltip
                    contents={t('multiGpuDeployment.tooltip.message')}
                    contentsAlign={{ vertical: 'top' }}
                  />
                }
                disableErrorMsg
              >
                <Radio
                  name='isDeploymentMultiGpu'
                  options={booleanTypeOptions}
                  value={isDeploymentMultiGpu}
                  onChange={radioBtnHandler}
                  customStyle={{ marginBottom: '36px' }}
                />
              </InputBoxWithLabel>
            </div>
          </div>
        )}
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(BuiltinModelFormModal);
