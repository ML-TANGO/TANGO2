import { useTranslation } from 'react-i18next';

import { InputText, Selectbox, Textarea } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import HuggingFaceSearch from '@src/components/molecules/HuggingFaceSearch';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import JonathanModelSearch from '@src/components/molecules/JonathanModelSearch';
import MultiSelect from '@src/components/molecules/MultiSelect';
import ResourceSetting from '@src/components/molecules/ResourceSetting';

// Components
import ModalFrame from '../ModalFrame';
import LoadTrainingSearch from './LoadTrainingSearch';

// CSS module
import classNames from 'classnames/bind';
import style from './DeploymentFormModal.module.scss';

const cx = classNames.bind(style);

const DeploymentFormModal = ({
  validate,
  data,
  type,
  deploymentName, // 배포 이름
  deploymentNameError, // 배포 이름 에러 텍스트
  deploymentDesc, // 배포 설명 텍스트
  deploymentDescError, // 배포 설명 에러 텍스트
  workspaceOptions, // 워크스페이스 옵션
  footerMessage,
  workspace,
  deploymentType, // 선택된 배포 타입
  radioBtnHandler, // 배포 타입 라디오 버튼 이벤트 핸들러
  textInputHandler, // 텍스트 인풋 이벤트 핸들러
  selectInputHandler, // 셀렉트 인풋 이벤트 핸들러
  accessTypeOptions, // access type 옵션
  accessType, // 선택된 access type
  ownerOptions, // owner 셀렉트 옵션
  owner, // 선택된 owner
  multiSelectHandler, // 멀티 셀렉트 이벤트 핸들러
  userList,
  selectedList,
  permissionLevel,
  gpuSelectedOptions,
  checkboxHandler,
  onChangeGpuInputValue,
  onSubmit,
  instanceList,
  gpuInputValues,
  modelSelectType,
  modelSelectOptions,
  jonathanSelectValue,
  huggingSelectValue,
  jonathanIntelligenceType,
  jonathanIntelligenceOptions,
  handleBuiltInValue,
  /// *
  jonathanTraining,
  jonathanModel,
  huggingTraining,
  huggingModel,
  handleHuggingFaceToken,
  huggingFaceToken,
}) => {
  const { t } = useTranslation();

  const { submit, cancel, workspaceId } = data;

  instanceList = instanceList.map((el) => {
    return {
      ...el,
      gpu_name: el.type === 'GPU' ? el.name : null,
    };
  });

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const title =
    type === 'CREATE_DEPLOYMENT'
      ? t('createDeploymentForm.title.label')
      : t('editDeploymentForm.title.label');

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={title}
      headerTitle={title}
      footerMessage={footerMessage}
      customStyle={{
        width: '664px',
      }}
    >
      <div className={cx('form')}>
        <div className={cx('row')}>
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
              isReadOnly={type === 'EDIT_DEPLOYMENT'}
              disableLeftIcon
              disableClearBtn
              isLowercase
              options={{ maxLength: 50 }}
              autoFocus={true}
              customStyle={{ fontSize: '14px' }}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('deploymentDescription.label')}
            optionalText={t('optional.label')}
            labelSize='large'
            optionalSize='small'
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
              customStyle={{ fontSize: '14px' }}
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
                isReadOnly={type === 'EDIT_DEPLOYMENT'}
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
          <InputBoxWithLabel
            labelText={t('deploymentsOption.label')}
            labelSize='large'
            // errorMsg={t(descriptionError)}
          >
            <ResourceSetting
              // ** 인스턴스 설정 [가져다 붙임] **
              isInstance
              models={instanceList}
              checkboxHandler={checkboxHandler}
              gpuSelectedOptions={gpuSelectedOptions}
              onChangeGpuInputValue={onChangeGpuInputValue}
              inputValue={gpuInputValues}
              edit={type === 'EDIT_DEPLOYMENT'}
              type={type}
            />
          </InputBoxWithLabel>
        </div>

        {/* 모델 유형 */}
        <div className={cx('row')}>
          <InputBoxWithLabel labelText={t('modelType.label')} labelSize='large'>
            <Radio
              name='modelSelectType'
              options={modelSelectOptions}
              value={modelSelectType}
              onChange={radioBtnHandler}
              readOnly={type === 'EDIT_DEPLOYMENT'}
              isLabelColor
            />
          </InputBoxWithLabel>

          {/** 모델 선택 */}
          {modelSelectType !== 1 && (
            <InputBoxWithLabel
              labelText={t('dataAnnotationPopup.step1.title')}
              labelSize='large'
            >
              <Radio
                name='jonathanIntelligenceType'
                options={jonathanIntelligenceOptions}
                value={jonathanIntelligenceType}
                onChange={radioBtnHandler}
                readOnly={type === 'EDIT_DEPLOYMENT'}
                isLabelColor
              />

              {modelSelectType === 0 && jonathanIntelligenceType === 0 && (
                <LoadTrainingSearch
                  selectCategory={jonathanTraining}
                  setSelectCategory={(v) =>
                    handleBuiltInValue(v, 'jonathanTraining')
                  }
                  setSelectModel={(v) => handleBuiltInValue(v, 'jonathanModel')}
                  selectModel={jonathanModel}
                  workspaceId={workspaceId}
                  getTrainingUrl={'/options/built-in-model/training'}
                  editMode={type === 'EDIT_DEPLOYMENT'}
                  style={{ marginTop: '20px' }}
                />
              )}
              {modelSelectType === 0 && jonathanIntelligenceType === 1 && (
                <JonathanModelSearch
                  selectCategory={jonathanTraining}
                  setSelectCategory={(v) =>
                    handleBuiltInValue(v, 'jonathanTraining')
                  }
                  setSelectModel={(v) => handleBuiltInValue(v, 'jonathanModel')}
                  selectModel={jonathanModel}
                  disabled={type === 'EDIT_DEPLOYMENT'}
                  style={{ marginTop: '20px' }}
                />
              )}
              {modelSelectType === 2 && jonathanIntelligenceType === 0 && (
                <LoadTrainingSearch
                  setSelectCategory={(v) =>
                    handleBuiltInValue(v, 'huggingTraining')
                  }
                  setSelectModel={(v) => handleBuiltInValue(v, 'huggingModel')}
                  selectCategory={huggingTraining}
                  selectModel={huggingModel}
                  workspaceId={workspaceId}
                  getTrainingUrl={'/options/huggingface/training'}
                  editMode={type === 'EDIT_DEPLOYMENT'}
                  style={{ marginTop: '20px' }}
                />
              )}
              {modelSelectType === 2 && jonathanIntelligenceType === 1 && (
                <HuggingFaceSearch
                  setSelectCategory={(v) =>
                    handleBuiltInValue(v, 'huggingTraining')
                  }
                  setSelectModel={(v) => handleBuiltInValue(v, 'huggingModel')}
                  selectCategory={huggingTraining}
                  selectModel={huggingModel}
                  huggingFaceToken={huggingFaceToken}
                  handleHuggingFaceToken={handleHuggingFaceToken}
                  disabled={type === 'EDIT_DEPLOYMENT'}
                  style={{ marginTop: '20px' }}
                />
              )}
            </InputBoxWithLabel>
          )}
        </div>
        <div className={cx('row', 'flex-cont')}>
          <InputBoxWithLabel
            labelText={t('accessType.label')}
            labelSize='large'
          >
            <Radio
              name='accessType'
              options={accessTypeOptions}
              value={accessType}
              onChange={radioBtnHandler}
              readOnly={permissionLevel > 3 && type === 'EDIT_DEPLOYMENT'}
              isLabelColor
            />
          </InputBoxWithLabel>
          <InputBoxWithLabel labelText={t('owner.label')} labelSize='large'>
            <Selectbox
              type='search'
              size='large'
              list={ownerOptions}
              placeholder={t('owner.placeholder')}
              selectedItem={owner}
              newSelectedItem={owner}
              newSelectedItemF
              onChange={(value) => {
                selectInputHandler('owner', value);
              }}
              isReadOnly={permissionLevel > 3 && type === 'EDIT_DEPLOYMENT'}
              customStyle={{
                fontStyle: {
                  selectbox: {
                    color:
                      permissionLevel > 3 && type === 'EDIT_DEPLOYMENT'
                        ? '#747474'
                        : '#121619',
                    textShadow: 'None',
                    fontSize: '14px',
                    width: '202px',
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
        <div className={cx('row')}></div>
        {accessType === 0 && (
          <div className={cx('row')}>
            <MultiSelect
              label='users.label'
              listLabel='availableUsers.label'
              selectedLabel='chosenUsers.label'
              list={userList} // 초기 목록
              selectedList={selectedList} // 초기 선택된 목록
              onChange={multiSelectHandler} // 변경 이벤트
              exceptItem={owner && owner.value} // 목록에서 빠질 아이템
              optional
              readOnly={permissionLevel > 3 && type === 'EDIT_DEPLOYMENT'}
            />
          </div>
        )}
      </div>
    </ModalFrame>
  );
};

export default DeploymentFormModal;
