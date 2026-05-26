import { useTranslation } from 'react-i18next';

// Components
import { Button, InputText, Textarea } from '@jonathan/ui-react';
import GroupList from './GroupList';
import TemplateList from './TemplateList';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Icons
import PlusIcon from '@src/static/images/icon/00-ic-basic-plus-blue.svg';
import ArrowIcon from '@src/static/images/icon/ic-arrow-down-blue.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './GroupSelectBox.module.scss';

const cx = classNames.bind(style);

/**
 * 템플릿 그룹 선택 박스
 */
function GroupSelectBox({
  clickedDataList,
  groupSelect,
  groupData,
  type,
  makeNewGroup,
  templateData,
  onClickGroupList,
  onClickTemplateList,
  clickedTemplateLists,
  onClickGroupSelect,
  onClickNewGroup,
  defaultGroupName,
  newGroupName,
  newGroupDescription,
  groupNameInputHandler,
  groupDescriptionInputHandler,
  groupNameDuplicate,
  templateEditData,
  goupOnClickNoGroup,
  templateNogroupSelected,
}) {
  const { t } = useTranslation();

  const TemplateArea = () => {
    return (
      <>
        <p className={cx('label')}>
          {t('template.templateHeaderSelectedTitle.label')}
        </p>
        <div className={cx('template-info')}>
          {t('template.newTemplate.description.label')}
        </div>
      </>
    );
  };

  const TemplateGroupName = () => {
    let returnData = '';
    if (
      !clickedDataList &&
      templateEditData?.deployment_template_group_id &&
      !makeNewGroup
    ) {
      groupData.forEach((g) => {
        if (g.id === templateEditData.deployment_template_group_id) {
          return (returnData = g.name);
        }
      });
    } else if (clickedDataList) {
      returnData = clickedDataList.name;
    } else if (makeNewGroup) {
      returnData = t('template.TempBodyGroupButton.label');
    } else {
      returnData = t('template.templateGroupSelect.message');
    }
    return returnData;
  };

  return (
    <>
      <div>
        {type === 'deployment' ? (
          <label className={cx('title')}>
            {t('template.templateGroup.label')} -{' '}
            {t('template.deployModal.option.label')}
          </label>
        ) : (
          <InputBoxWithLabel
            labelText={t('template.group.label')}
            optionalText={t('optional.label')}
            labelSize='large'
            optionalSize='large'
            disableErrorMsg
          />
        )}
      </div>
      <div
        className={cx(
          'select-closed-container',
          groupSelect && 'select-open-container',
        )}
      >
        <p
          className={cx(
            (templateEditData?.deployment_template_group_id || makeNewGroup) &&
              'group-name',
          )}
        >
          <TemplateGroupName />
        </p>
        <p onClick={() => onClickGroupSelect()}>
          {t('template.templateGroupSelectBtn.label')}
          <img
            className={cx(groupSelect ? 'arrow-open-icon' : 'arrow-close-icon')}
            src={ArrowIcon}
            alt='icon'
          />
        </p>
      </div>
      <div
        className={cx('template-select', groupSelect && 'group-select-area')}
      >
        <div>
          <div className={cx('group-container')}>
            <Button
              type='primary-reverse'
              icon={PlusIcon}
              onClick={onClickNewGroup}
              customStyle={{
                paddingLeft: '8px',
                width: '100%',
                height: '42px',
                justifyContent: 'inherit',
                backgroundColor: makeNewGroup && '#f9fafb',
                borderRadius: '2px',
                border: makeNewGroup
                  ? '1px solid #c8dbfd'
                  : '1px solid transparent',
                fontFamily: 'SpoqaB',
              }}
              iconStyle={{ width: '16px' }}
            >
              {t('template.TempBodyGroupButton.label')}
            </Button>
            <GroupList
              groupData={groupData}
              clickedDataList={clickedDataList}
              onClickGroupList={onClickGroupList}
              noGroupSelectedStatus={templateNogroupSelected}
              onClickNoGroup={goupOnClickNoGroup}
              t={t}
            />
          </div>
          <div className={cx('template-container')}>
            <TemplateList
              clickedTemplateLists={clickedTemplateLists}
              templateData={templateData}
              makeNewGroup={makeNewGroup}
              onClickTemplateList={onClickTemplateList}
              originTemplateData={templateData}
              clickedDataList={clickedDataList}
            />
            {makeNewGroup && !clickedDataList && (
              <div className={cx('create-group-container')}>
                <div className={cx('row')}>
                  <label className={cx('title-container')}>
                    <p className={cx('name')}>
                      {t('template.groupCreateName.label')}
                    </p>
                    <p className={cx('count')}>
                      <span className={cx('blue')}>{newGroupName.length}</span>
                      /50
                    </p>
                  </label>
                  <InputText
                    size='medium'
                    name='groupName'
                    status={groupNameDuplicate ? 'error' : 'default'}
                    value={newGroupName}
                    options={{ maxLength: 50 }}
                    placeholder={defaultGroupName}
                    onChange={groupNameInputHandler}
                    onClear={() => {
                      groupNameInputHandler({
                        target: { value: '', name: 'groupName' },
                      });
                    }}
                    customStyle={{
                      marginBottom: '4px',
                    }}
                    disableLeftIcon={true}
                    disableClearBtn={true}
                    autoFocus
                  />
                  <div className={cx('error-message')}>
                    {groupNameDuplicate && t(groupNameDuplicate)}
                  </div>
                </div>
                <div className={cx('row')}>
                  <label className={cx('title-container')}>
                    <p className={cx('name')}>
                      {t('template.group.description.label')} -{' '}
                      {t('template.deployModal.option.label')}
                    </p>
                    <p className={cx('count')}>
                      <span className={cx('blue')}>
                        {newGroupDescription.length}
                      </span>
                      /1000
                    </p>
                  </label>
                  <Textarea
                    size='medium'
                    placeholder={t(
                      'template.groupCreateInputDescription.label',
                    )}
                    value={newGroupDescription}
                    name='deploymentDesc'
                    onChange={groupDescriptionInputHandler}
                  />
                </div>
                {!makeNewGroup && <TemplateArea />}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
export default GroupSelectBox;
