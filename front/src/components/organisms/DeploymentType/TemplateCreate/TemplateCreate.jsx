// Components
import { InputText, Textarea, Tooltip } from '@jonathan/ui-react';
import GroupSelectBox from '@src/components/organisms/GroupSelectBox';

// CSS Module
import classNames from 'classnames/bind';
import style from './TemplateCreate.module.scss';
import { useTranslation } from 'react-i18next';

const cx = classNames.bind(style);

function TemplateCreate({
  groupData,
  clickedDataList,
  clickedTemplateLists,
  setClickedDataList,
  workspaceId,
  setMakeNewGroup,
  makeNewGroup,
  templateData,
  getTemplateListHandler,
  setClickedTemplateLists,
  onClickGroupList,
  onClickTemplateList,
  onClickGroupSelect,
  groupSelect,
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
  defaultGroupName,
  defaultTemplateName,
  templateOpenStatus,
  onClickTemplateBox,
}) {
  const { t } = useTranslation();

  return (
    <>
      <div className={cx('template-container')}>
        <div className={cx('header')}>
          <div className={cx('title')}>
            <span>{t('template.label')}</span>
            <Tooltip
              title={t('Template')}
              contents={t('template.tooltip.description.message')}
              globalCustomStyle={{ width: '330px' }}
            />
          </div>
          <div
            onClick={onClickTemplateBox}
            className={cx(templateOpenStatus ? 'cancel' : 'save')}
          >
            {templateOpenStatus ? t('cancel.label') : t('template.save.label')}
          </div>
        </div>
        <div
          className={cx(
            templateOpenStatus ? 'body-close' : 'body-open',
            'body',
          )}
        >
          <div className={cx('row')}>
            <div className={cx('title-container')}>
              <label className={cx('name')}>
                {t('template.deployModal.name.label')}
              </label>
              <span className={cx('count')}>
                <span className={cx('blue')}>{templateNewName.length}</span>
                /50
              </span>
            </div>
            <InputText
              size='large'
              name='imageName'
              options={{ maxLength: 50 }}
              placeholder={defaultTemplateName}
              customStyle={{
                marginBottom: '10px',
              }}
              disableLeftIcon={true}
              disableClearBtn={true}
              onChange={templateNewNameInputHandler}
              onClear={() => {
                templateNewNameInputHandler({
                  target: { value: '', name: 'groupName' },
                });
              }}
              value={templateNewName}
              status={templateNameDuplicate ? 'error' : 'default'}
            />
            <div className={cx('error-message')}>
              {templateNameDuplicate && t(templateNameDuplicate)}
            </div>
          </div>
          <div className={cx('row')}>
            <div className={cx('title-container')}>
              <label className={cx('name')}>
                {t('template.deployModal.description.label')} -{' '}
                {t('template.deployModal.option.label')}
              </label>
              <span className={cx('count')}>
                <span className={cx('blue')}>
                  {templateNewDescription?.length}
                </span>
                /1000
              </span>
            </div>
            <Textarea
              onChange={templateNewDescriptionInputHandler}
              size='large'
              name='deploymentDesc'
              value={templateNewDescription}
            />
          </div>
          <GroupSelectBox
            clickedDataList={clickedDataList}
            setClickedDataList={setClickedDataList}
            groupSelect={groupSelect}
            setClickedTemplateLists={setClickedTemplateLists}
            clickedTemplateLists={clickedTemplateLists}
            groupData={groupData}
            workspaceId={workspaceId}
            type={'deployment'}
            setMakeNewGroup={setMakeNewGroup}
            makeNewGroup={makeNewGroup}
            templateData={templateData}
            getTemplateListHandler={getTemplateListHandler}
            onClickGroupList={onClickGroupList}
            onClickTemplateList={onClickTemplateList}
            onClickGroupSelect={onClickGroupSelect}
            onClickNewGroup={onClickNewGroup}
            groupNameInputHandler={groupNameInputHandler}
            newGroupName={newGroupName}
            newGroupDescription={newGroupDescription}
            groupNameDuplicate={groupNameDuplicate}
            groupDescriptionInputHandler={groupDescriptionInputHandler}
            defaultGroupName={defaultGroupName}
          />
        </div>
      </div>
    </>
  );
}
export default TemplateCreate;
