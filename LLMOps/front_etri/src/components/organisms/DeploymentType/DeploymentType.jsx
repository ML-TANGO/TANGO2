// components
import { Button } from '@tango/ui-react';

import builtInImage from '@src/static/images/icon/ic-builtIn-gray.svg';
import jsonImage from '@src/static/images/icon/ic-json-gray.svg';
import templateImage from '@src/static/images/icon/ic-template-gray.svg';
// images
import trainingImage from '@src/static/images/icon/icon-trainings-gray.svg';
import { useDispatch } from 'react-redux';

import CustomButton from '@src/components/atoms/button/Button';

import { closeModal, openModal } from '@src/store/modules/modal';

import BuiltInType from './BuiltInType';
import JsonType from './JsonType';
import TemplateCreate from './TemplateCreate';
import TemplateType from './TemplateType';
import TrainingType from './TrainingType';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeploymentType.module.scss';

const cx = classNames.bind(style);

function DeploymentType({
  type,
  selectedDeploymentType,
  deploymentTypeHandler,
  trainingSelectedType,
  trainingSelectedOwner,
  trainingTypeSelectHandler,
  trainingSearch,
  trainingSortHandler,
  trainingInputValue,
  trainingList,
  backBtnHandler,
  tabClickHandler,
  getJobList,
  jobDetailList,
  toolDetailOpenHandler,
  jobList,
  jobDetailOpenList,
  trainingToolTab,
  trainingToolTabHandler,
  hpsList,
  hpsDetailList,
  hpsDetailOpenList,
  selectedTool,
  selectedToolType,
  toolSelectHandler,
  trainingSelectHandler,
  selectedTraining,
  trainingType,
  getCustomList,
  customParam,
  paramsInputHandler,
  customRuncode,
  runcodeClickHandler,
  customFile,
  variablesAdd,
  variablesDelete,
  variablesValues,
  variableInputHandler,
  variablesSortHandler,
  customSearchValue,
  customLan,
  getJobs,
  selectedHpsScore,
  selectedHps,
  hpsLogTable,
  customList,
  groupData,
  workspaceId,
  componentType,
  templateData,
  makeNewGroup,
  clickedDataList,
  clickedTemplateLists,
  groupSelect,
  onClickGroupSelect,
  setClickedDataList,
  setMakeNewGroup,
  onClickGroupList,
  onClickTemplateList,
  getTemplateListHandler,
  onClickNewGroup,
  groupNameInputHandler,
  newGroupName,
  newGroupDescription,
  groupNameDuplicate,
  groupDescriptionInputHandler,
  templateNewNameInputHandler,
  templateNewDescriptionInputHandler,
  templateNewName,
  templateNewDescription,
  templateNameDuplicate,
  applyButtonClicked,
  defaultGroupName,
  defaultTemplateName,
  toolSortHandler,
  toolSearchValue,
  toolSelectedOwner,
  onClickTemplateBox,
  templateOpenStatus,
  customListStatus,
  hpsLogSortHandler,
  selectedHpsId,
  selectedLogId,
  logClickHandler,
  selectedTrainingData,
  toolModelSearchValue,
  toolModelSortHandler,
  hpsModelList,
  jobModelList,
  hpsModelSelectValue,
  jobModelSelectValue,
  toolModelSelectHandler,
  trainingTypeArrow,
  trainingTypeArrowHandler,
  builtInModelsList,
  modelList,
  searchModelHandler,
  modelCategorySelect,
  categoryHandler,
  onClickModelList,
  modelSelectStatus,
  modelSelectStatusHanlder,
  selectedModel,
  jsonDataHandler,
  editStatus,
  jsonData,
  showSelectAgain,
  readOnly,
  jsonDataErrorHandler,
  innerRef,
  onClickNoGroup,
  deploymentNoGroupSelected,
  workerSettingType,
  t,
  resetCustomInputAndEnvironments,
}) {
  const dispatch = useDispatch();

  const selectedTypeHandler = (type) => {
    switch (type) {
      case 'usertrained':
        return t('deploymentTypeTraining.label');
      case 'pretrained':
        return t('deploymentTypeBuiltIn.label');
      case 'template':
        return t('deploymentTypeTemplate.label');
      case 'sandbox':
        return t('deploymentTypeSetting.label');
      default:
        break;
    }
  };

  const openCreateApiCodeModal = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_DEPLOYMENT_API',
        modalData: {
          submit: {
            text: t('create.label'),
            func: () => {
              closeModal('CREATE_DEPLOYMENT_API');
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
        },
      }),
    );
  };

  const typeOption = [
    {
      title: t('deploymentTypeTraining.label'),
      describe: t('deploymentTypeTraining.desc'),
      type: 'usertrained',
      image: trainingImage,
      style: { height: '28px' },
    },
    // {
    //   title: t('deploymentTypeBuiltIn.label'),
    //   describe: t('deploymentTypeBuiltIn.desc'),
    //   type: 'pretrained',
    //   image: builtInImage,
    // },
    // {
    //   title: t('deploymentTypeSetting.label'),
    //   describe: t('deploymentTypeSetting.desc'),
    //   type: 'sandbox',
    //   image: jsonImage,
    // },
    // {
    //   title: t('deploymentTypeTemplate.label'),
    //   describe: t('deploymentTypeTemplate.desc'),
    //   type: 'template',
    //   image: templateImage,
    // },
  ];
  return (
    <>
      <div className={cx('row', 'deployment-type-row')}>
        <div className={cx('title-label')}>
          {t(
            workerSettingType || selectedDeploymentType
              ? 'deployApiCodeExecution.label'
              : 'deploymentType.label',
          )}
        </div>
        {selectedDeploymentType &&
          !workerSettingType &&
          type !== 'EDIT_WORKER' && (
            <div className={cx('back-btn-box')}>
              <div className={cx('back-title')}>
                {t('selected.label')} :{' '}
                {selectedTypeHandler(selectedDeploymentType)}
              </div>
              {!showSelectAgain && (
                <Button
                  type='red-reverse'
                  customStyle={{ padding: '10px', marginLeft: '7px' }}
                  onClick={() => backBtnHandler()}
                >
                  {t('selectAgain.label')}
                </Button>
              )}
            </div>
          )}
        <span className={cx('api-deploy-btn')} onClick={openCreateApiCodeModal}>
          + {t('createDeploymentApiCode.label')}
        </span>
      </div>
      <div className={cx('container')}>
        {!selectedDeploymentType && (
          <div className={cx('type-box')}>
            {typeOption.map((option, idx) => {
              return (
                <div
                  className={cx('type')}
                  onClick={() => deploymentTypeHandler(option.type)}
                  key={idx}
                >
                  <div className={cx('title-box')}>
                    <div className={cx('image')}>
                      <img src={option.image} alt='' style={option?.style} />
                    </div>
                    <div className={cx('title')}>{option.title}</div>
                  </div>
                  <div className={cx('desc')}>{option.describe}</div>
                </div>
              );
            })}
          </div>
        )}
        {(selectedDeploymentType === 'usertrained' ||
          selectedDeploymentType === 'custom') && (
          <TrainingType
            type={type}
            trainingList={trainingList}
            trainingSelectedType={trainingSelectedType}
            trainingSelectedOwner={trainingSelectedOwner}
            trainingTypeSelectHandler={trainingTypeSelectHandler}
            trainingSearch={trainingSearch}
            trainingSortHandler={trainingSortHandler}
            trainingInputValue={trainingInputValue}
            getJobList={getJobList}
            tabClickHandler={tabClickHandler}
            jobDetailList={jobDetailList}
            toolDetailOpenHandler={toolDetailOpenHandler}
            jobDetailOpenList={jobDetailOpenList}
            jobList={jobList}
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
            customParam={customParam}
            paramsInputHandler={paramsInputHandler}
            customRuncode={customRuncode}
            customFile={customFile}
            runcodeClickHandler={runcodeClickHandler}
            variablesAdd={variablesAdd}
            variablesDelete={variablesDelete}
            variablesValues={variablesValues}
            variableInputHandler={variableInputHandler}
            variablesSortHandler={variablesSortHandler}
            customSearchValue={customSearchValue}
            customLan={customLan}
            customList={customList}
            getJobs={getJobs}
            hpsLogTable={hpsLogTable}
            selectedHpsScore={selectedHpsScore}
            selectedHps={selectedHps}
            toolSortHandler={toolSortHandler}
            toolSearchValue={toolSearchValue}
            toolSelectedOwner={toolSelectedOwner}
            customListStatus={customListStatus}
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
            editStatus={editStatus}
            trainingTypeArrowHandler={trainingTypeArrowHandler}
            resetCustomInputAndEnvironments={resetCustomInputAndEnvironments}
            t={t}
            readOnly={readOnly}
          />
        )}
        {selectedDeploymentType === 'pretrained' && (
          <BuiltInType
            modelList={modelList}
            builtInModelsList={builtInModelsList}
            modelCategorySelect={modelCategorySelect}
            categoryHandler={categoryHandler}
            searchModelHandler={searchModelHandler}
            onClickModelList={onClickModelList}
            modelSelectStatus={modelSelectStatus}
            modelSelectStatusHanlder={modelSelectStatusHanlder}
            selectedModel={selectedModel}
            editStatus={editStatus}
            readOnly={readOnly}
            t={t}
          />
        )}
        {/* {selectedDeploymentType === 'sandbox' && (
          <JsonType
            jsonData={jsonData}
            editStatus={editStatus}
            jsonDataHandler={jsonDataHandler}
            readOnly={readOnly}
            jsonDataErrorHandler={jsonDataErrorHandler}
            innerRef={innerRef}
          />
        )}
        {selectedDeploymentType === 'template' && (
          <TemplateType
            makeNewGroup={makeNewGroup}
            templateData={templateData}
            groupData={groupData}
            clickedDataList={clickedDataList}
            clickedTemplateLists={clickedTemplateLists}
            onClickGroupList={onClickGroupList}
            onClickTemplateList={onClickTemplateList}
            type={selectedDeploymentType}
            applyButtonClicked={applyButtonClicked}
            onClickNoGroup={onClickNoGroup}
            deploymentNoGroupSelected={deploymentNoGroupSelected}
          />
        )} */}
        {/* {selectedDeploymentType &&
          selectedDeploymentType !== 'template' &&
          componentType === 'deployment' && (
            <TemplateCreate
              groupData={groupData}
              clickedDataList={clickedDataList}
              clickedTemplateLists={clickedTemplateLists}
              setClickedDataList={setClickedDataList}
              workspaceId={workspaceId}
              componentType={componentType}
              setMakeNewGroup={setMakeNewGroup}
              makeNewGroup={makeNewGroup}
              templateData={templateData}
              getTemplateListHandler={getTemplateListHandler}
              onClickGroupList={onClickGroupList}
              onClickTemplateList={onClickTemplateList}
              onClickGroupSelect={onClickGroupSelect}
              groupSelect={groupSelect}
              onClickNewGroup={onClickNewGroup}
              groupNameInputHandler={groupNameInputHandler}
              newGroupName={newGroupName}
              newGroupDescription={newGroupDescription}
              groupNameDuplicate={groupNameDuplicate}
              groupDescriptionInputHandler={groupDescriptionInputHandler}
              templateNewNameInputHandler={templateNewNameInputHandler}
              templateNewDescriptionInputHandler={
                templateNewDescriptionInputHandler
              }
              templateNewName={templateNewName}
              templateNewDescription={templateNewDescription}
              templateNameDuplicate={templateNameDuplicate}
              defaultGroupName={defaultGroupName}
              defaultTemplateName={defaultTemplateName}
              templateOpenStatus={templateOpenStatus}
              onClickTemplateBox={onClickTemplateBox}
            />
          )} */}
      </div>
    </>
  );
}

export default DeploymentType;
