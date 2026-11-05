import { useState } from 'react';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, InputText } from '@jonathan/ui-react';
import GroupList from '@src/components/organisms/GroupSelectBox/GroupList';
import TemplateList from '@src/components/organisms/GroupSelectBox/TemplateList';

// CSS Module
import style from './TemplateType.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function TemplateType({
  groupData,
  clickedDataList,
  onClickGroupList,
  templateData,
  makeNewGroup,
  onClickTemplateList,
  clickedTemplateLists,
  type,
  applyButtonClicked,
  onClickNoGroup,
  deploymentNoGroupSelected,
}) {
  const { t } = useTranslation();
  const [searchGroupData, setSearchGroupData] = useState(null);
  const [searchTemplateData, setSearchTemplateData] = useState(null);

  const searchGroupName = (e) => {
    const value = e.target.value;
    let filteredData = groupData.filter((data) => {
      return (
        data.descriptionAssemble?.indexOf(value) >= 0 ||
        data.name?.indexOf(value) >= 0 ||
        data.user_name?.indexOf(value) >= 0 ||
        (data.description?.indexOf(value) >= 0 && data)
      );
    });
    setSearchGroupData(filteredData);
  };
  const searchTemplateName = (e) => {
    const value = e.target.value;
    let filteredData = templateData.filter((data) => {
      return data.name?.indexOf(value) >= 0 && data;
    });
    setSearchTemplateData(filteredData);
  };

  return (
    <div className={cx('container')}>
      <div className={cx('group-container')}>
        <div className={cx('search-box')}>
          <InputText
            onChange={(e) => searchGroupName(e)}
            disableLeftIcon={false}
            placeholder={`${t('groupName.label')}, ${t('description.label')}`}
          />
        </div>
        <div className={cx('contents')}>
          {groupData?.length > 0 ? (
            <GroupList
              type={type}
              groupData={searchGroupData || groupData}
              clickedDataList={clickedDataList}
              onClickGroupList={onClickGroupList}
              onClickNoGroup={onClickNoGroup}
              noGroupSelectedStatus={deploymentNoGroupSelected}
              t={t}
            />
          ) : (
            <div className={cx('empty-list')}>
              {t('template.group.empty.message')}
            </div>
          )}
        </div>
      </div>
      <div className={cx('template-container')}>
        <div className={cx('search-box')}>
          <InputText
            onChange={(e) => searchTemplateName(e)}
            disableLeftIcon={false}
            placeholder={t('template.deployModal.name.label')}
          />
        </div>
        <div className={cx('contents')}>
          <TemplateList
            templateData={searchTemplateData || templateData}
            makeNewGroup={makeNewGroup}
            clickedTemplateLists={clickedTemplateLists}
            onClickTemplateList={onClickTemplateList}
            type={type}
            originTemplateData={templateData}
            clickedDataList={clickedDataList}
          />
        </div>
        <Button
          customStyle={{
            position: 'absolute',
            bottom: '0px',
            width: '100%',
            borderRadius: '0px',
            height: '45px',
          }}
          disabled={
            (clickedDataList && clickedTemplateLists) ||
            (!clickedDataList && clickedTemplateLists)
              ? false
              : true
          }
          onClick={applyButtonClicked}
        >
          {t('template.apply.btn.label')}
        </Button>
      </div>
    </div>
  );
}

export default TemplateType;
