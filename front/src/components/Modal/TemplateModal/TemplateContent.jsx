// i18n
import { useTranslation } from 'react-i18next';

// Compontents
import { InputText, Textarea } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import GroupSelectBox from '@src/components/organisms/GroupSelectBox';
import DeploymentType from '@src/components/organisms/DeploymentType';

// CSS Module
import classNames from 'classnames/bind';
import style from './TemplateContent.module.scss';
const cx = classNames.bind(style);

function TemplateContent({
  onClickNewGroup,
  deploymentTypeHandler,
  onClickGroupList,
  onClickGroupSelect,
  onClickDeployTemplateList,
  onClickDeploySelect,
  onClickDeployList,
  onClickGroupTemplateList,
  groupTemplateData,
  deployTemplateData,
  deploymentType,
  makeNewGroup,
  workspaceId,
  groupData,
  groupSelect,
  getTemplateListHandler,
  setMakeNewGroup,
  setClickedDeployDataList,
  clickedDeployDataList,
  clickedDeployTemplateLists,
  clickedGroupTemplateLists,
  clickedGroupDataList,
  newTemplateName,
  nameInputHandler,
  newTemplateDescription,
  descriptionInputHandler,
  defaultGroupName,
  templateNameDuplicate,
  newGroupName,
  newGroupDescription,
  groupNameInputHandler,
  groupDescriptionInputHandler,
  groupNameDuplicate,
  trainingTypeSelectHandler,
  trainingSortHandler,
  getCustomList,
  variablesSortHandler,
  selectedDeploymentType,
  trainingList,
  trainingInputValue,
  trainingSelectTab,
  jobDetailList,
  jobList,
  originJobList,
  trainingToolTab,
  hpsList,
  originHpsList,
  hpsDetailList,
  hpsLogTable,
  selectedHpsScore,
  selectedHps,
  customLan,
  customFile,
  customParam,
  customList,
  customSearchValue,
  customRuncode,
  selectedTool,
  selectedToolType,
  trainingType,
  ownerOptions,
  selectedTraining,
  hpsDetailOpenList,
  jobDetailOpenList,
  trainingSelectedType,
  trainingSelectedOwner,
  variablesValues,
  getJobList,
  backBtnHandler,
  toolSelectHandler,
  toolDetailOpenHandler,
  trainingToolTabHandler,
  toolSortHandler,
  toolSearchValue,
  toolSelectedOwner,
  runcodeClickHandler,
  modelList,
  modelSelectStatus,
  searchModelHandler,
  modelCategorySelect,
  categoryHandler,
  onClickModelList,
  selectedModel,
  modelSelectStatusHanlder,
  jsonDataHandler,
  editStatus,
  jsonData,
  applyButtonClicked,
  showSelectAgain,
  trainingTypeArrowCustomHandler,
  trainingTypeArrowHandler,
  logClickHandler,
  hpsLogSortHandler,
  hpsModelList,
  jobModelList,
  originHpsModelList,
  originJobModelList,
  selectedLogId,
  toolModelSearchValue,
  hpsModelSelectValue,
  selectedHpsId,
  jobModelSelectValue,
  trainingTypeArrow,
  hpsLogList,
  variablesAdd,
  variablesDelete,
  variableInputHandler,
  paramsInputHandler,
  toolModelSelectHandler,
  toolModelSortHandler,
  customListStatus,
  readOnly,
  templateEditData,
  innerRef,
  jsonDataErrorHandler,
  onClickNoGroup,
  deploymentNoGroupSelected,
  goupOnClickNoGroup,
  templateNogroupSelected,
}) {
  const { t } = useTranslation();
  return (
    <div className={cx('container')}>
      <label className={cx('title-container')}>
        <span className={cx('name')}>
          {t('template.deployModal.name.label')}
        </span>
        <span className={cx('count')}>
          <span className={cx('blue')}>{newTemplateName.length}</span>/50
        </span>
      </label>
      <InputText
        size='large'
        name='imageName'
        status={templateNameDuplicate ? 'error' : 'default'}
        value={newTemplateName}
        options={{ maxLength: 50 }}
        placeholder={t('template.name.input.label')}
        onChange={nameInputHandler}
        onClear={() => {
          nameInputHandler({ target: { value: '', name: 'imageName' } });
        }}
        disableLeftIcon={true}
        disableClearBtn={true}
        autoFocus
      />
      <div className={cx('error-message')}>
        {templateNameDuplicate && t(templateNameDuplicate)}
      </div>
      <InputBoxWithLabel
        labelText={t('template.searchPlaceholderDescription.label')}
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='large'
        disableErrorMsg
      >
        <Textarea
          size='large'
          placeholder={t('template.groupCreateInputDescription.label')}
          value={newTemplateDescription}
          name='deploymentDesc'
          onChange={descriptionInputHandler}
          maxLength={1000}
          isShowMaxLength
          customStyle={{
            marginBottom: '40px',
          }}
        />
      </InputBoxWithLabel>
      <GroupSelectBox
        clickedDataList={clickedGroupDataList}
        groupSelect={groupSelect}
        clickedTemplateLists={clickedGroupTemplateLists}
        templateData={groupTemplateData}
        groupData={groupData}
        workspaceId={workspaceId}
        makeNewGroup={makeNewGroup}
        onClickGroupList={onClickGroupList}
        onClickGroupSelect={onClickGroupSelect}
        onClickTemplateList={onClickGroupTemplateList}
        onClickNewGroup={onClickNewGroup}
        defaultGroupName={defaultGroupName}
        newGroupName={newGroupName}
        newGroupDescription={newGroupDescription}
        groupNameInputHandler={groupNameInputHandler}
        groupDescriptionInputHandler={groupDescriptionInputHandler}
        groupNameDuplicate={groupNameDuplicate}
        editStatus={editStatus}
        templateEditData={templateEditData}
        goupOnClickNoGroup={goupOnClickNoGroup}
        templateNogroupSelected={templateNogroupSelected}
      />
      <div className={cx('deployment-type')}>
        <DeploymentType
          type={deploymentType}
          deploymentTypeHandler={deploymentTypeHandler}
          groupData={groupData}
          workspaceId={workspaceId}
          templateData={deployTemplateData}
          makeNewGroup={makeNewGroup}
          clickedDataList={clickedDeployDataList}
          clickedTemplateLists={clickedDeployTemplateLists}
          groupSelect={groupSelect}
          onClickGroupSelect={onClickDeploySelect}
          onClickTemplateList={onClickDeployTemplateList}
          onClickGroupList={onClickDeployList}
          setClickedDataList={setClickedDeployDataList}
          setMakeNewGroup={setMakeNewGroup}
          getTemplateListHandler={getTemplateListHandler}
          trainingTypeSelectHandler={trainingTypeSelectHandler}
          trainingSortHandler={trainingSortHandler}
          getCustomList={getCustomList}
          variablesSortHandler={variablesSortHandler}
          selectedDeploymentType={selectedDeploymentType}
          trainingList={trainingList}
          trainingInputValue={trainingInputValue}
          trainingSelectTab={trainingSelectTab}
          jobDetailList={jobDetailList}
          jobList={jobList}
          originJobList={originJobList}
          trainingToolTab={trainingToolTab}
          hpsList={hpsList}
          originHpsList={originHpsList}
          hpsDetailList={hpsDetailList}
          hpsLogTable={hpsLogTable}
          selectedHpsScore={selectedHpsScore}
          selectedHps={selectedHps}
          customLan={customLan}
          customFile={customFile}
          customParam={customParam}
          customList={customList}
          customSearchValue={customSearchValue}
          customRuncode={customRuncode}
          selectedTool={selectedTool}
          selectedToolType={selectedToolType}
          trainingType={trainingType}
          ownerOptions={ownerOptions}
          selectedTraining={selectedTraining}
          hpsDetailOpenList={hpsDetailOpenList}
          jobDetailOpenList={jobDetailOpenList}
          trainingSelectedType={trainingSelectedType}
          trainingSelectedOwner={trainingSelectedOwner}
          variablesValues={variablesValues}
          getJobList={getJobList}
          backBtnHandler={backBtnHandler}
          toolSelectHandler={toolSelectHandler}
          toolDetailOpenHandler={toolDetailOpenHandler}
          trainingToolTabHandler={trainingToolTabHandler}
          toolSortHandler={toolSortHandler}
          toolSearchValue={toolSearchValue}
          toolSelectedOwner={toolSelectedOwner}
          modelList={modelList}
          modelSelectStatus={modelSelectStatus}
          searchModelHandler={searchModelHandler}
          modelCategorySelect={modelCategorySelect}
          categoryHandler={categoryHandler}
          onClickModelList={onClickModelList}
          selectedModel={selectedModel}
          modelSelectStatusHanlder={modelSelectStatusHanlder}
          jsonDataHandler={jsonDataHandler}
          editStatus={editStatus}
          jsonData={jsonData}
          applyButtonClicked={applyButtonClicked}
          showSelectAgain={showSelectAgain}
          runcodeClickHandler={runcodeClickHandler}
          trainingTypeArrowCustomHandler={trainingTypeArrowCustomHandler}
          trainingTypeArrowHandler={trainingTypeArrowHandler}
          logClickHandler={logClickHandler}
          hpsLogSortHandler={hpsLogSortHandler}
          hpsModelList={hpsModelList}
          jobModelList={jobModelList}
          originHpsModelList={originHpsModelList}
          originJobModelList={originJobModelList}
          selectedLogId={selectedLogId}
          toolModelSearchValue={toolModelSearchValue}
          hpsModelSelectValue={hpsModelSelectValue}
          selectedHpsId={selectedHpsId}
          jobModelSelectValue={jobModelSelectValue}
          trainingTypeArrow={trainingTypeArrow}
          hpsLogList={hpsLogList}
          variablesDelete={variablesDelete}
          variablesAdd={variablesAdd}
          variableInputHandler={variableInputHandler}
          paramsInputHandler={paramsInputHandler}
          toolModelSelectHandler={toolModelSelectHandler}
          toolModelSortHandler={toolModelSortHandler}
          customListStatus={customListStatus}
          readOnly={readOnly}
          t={t}
          innerRef={innerRef}
          jsonDataErrorHandler={jsonDataErrorHandler}
          onClickNoGroup={onClickNoGroup}
          deploymentNoGroupSelected={deploymentNoGroupSelected}
        />
      </div>
    </div>
  );
}
export default TemplateContent;
