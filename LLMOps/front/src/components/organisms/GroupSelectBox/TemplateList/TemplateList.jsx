// i18n
import { useTranslation } from 'react-i18next';

// Components
import ListItem from './ListItem';

// CSS Module
import classNames from 'classnames/bind';
import style from './TemplateList.module.scss';

const cx = classNames.bind(style);

function TemplateList({
  templateData,
  makeNewGroup,
  clickedDataList,
  onClickTemplateList,
  clickedTemplateLists,
  type,
  originTemplateData,
}) {
  const { t } = useTranslation();
  const TemplateArea = () => {
    return (
      <>
        <p className={cx('label')}>{t('template')}</p>
        {type !== 'template' && (
          <div className={cx('template-info')}>
            {t('template.newTemplate.description.label')}
          </div>
        )}
      </>
    );
  };

  return (
    <div className={cx('clicked-list')}>
      {!makeNewGroup && (
        <>
          <p className={cx('label')}>{t('template.selectedGroup.label')}</p>
          <p className={cx('name')}>
            {clickedDataList?.name || t('template.templateHeaderTitle.label')}
          </p>
          <p className={cx('description')}>
            {clickedDataList && clickedDataList.description}
          </p>
          <TemplateArea />
          {originTemplateData?.length > 0
            ? templateData?.map((data) => {
                return (
                  <ListItem
                    key={data.id}
                    data={data}
                    type={type}
                    clickedTemplateLists={clickedTemplateLists}
                    onClickTemplateList={onClickTemplateList}
                  />
                );
              })
            : type === 'template' && (
                <div className={cx('empty-list')}>
                  {t('template.empty.message')}
                </div>
              )}
        </>
      )}
    </div>
  );
}
export default TemplateList;
