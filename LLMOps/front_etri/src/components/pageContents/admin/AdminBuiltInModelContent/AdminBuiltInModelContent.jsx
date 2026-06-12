// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Button, Selectbox } from '@tango/ui-react';
import PageTitle from '@src/components/atoms/PageTitle';
import Table from '@src/components/molecules/Table';

// CSS module
import style from './AdminBuiltInModelContent.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

function AdminBuiltInModelContent({
  columns,
  tableData,
  totalRows,
  searchKey,
  keyword,
  onSearchKeyChange,
  onSearch,
  onCreate,
  openDeleteConfirmPopup,
  modelType,
  onModelTypeChange,
  onSelect,
  deleteBtnDisabled,
  toggledClearRows,
  onClear,
  modelTypeOptions,
  onSortHandler,
}) {
  const { t } = useTranslation();

  const searchOptions = [
    { label: t('modelName.label'), value: 'name' },
    { label: t('modelDirectory.label'), value: 'path' },
    { label: t('dockerImage.label'), value: 'run_docker_name' },
    { label: t('creator.label'), value: 'created_by' },
  ];

  const filterList = (
    <>
      <Selectbox
        size='medium'
        list={modelTypeOptions}
        selectedItem={modelType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onModelTypeChange}
        t={t}
      />
    </>
  );

  const topButtonList = (
    <>
      <Button type='primary' onClick={onCreate}>
        {t('addBuiltinModel.label')}
      </Button>
    </>
  );

  const bottomButtonList = (
    <>
      <Button
        type='red'
        onClick={openDeleteConfirmPopup}
        disabled={deleteBtnDisabled}
      >
        {t('delete.label')}
      </Button>
    </>
  );

  return (
    <div id='AdminBuiltInModelContent'>
      <PageTitle>{t('builtInModels.label')}</PageTitle>
      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={totalRows}
          topButtonList={topButtonList}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          onSelect={onSelect}
          defaultSortField='create_datetime'
          toggledClearRows={toggledClearRows}
          filterList={filterList}
          searchOptions={searchOptions}
          searchKey={searchKey}
          keyword={keyword}
          onSearchKeyChange={onSearchKeyChange}
          onSearch={(e) => {
            onSearch(e.target.value);
          }}
          onClear={onClear}
          onSortHandler={onSortHandler}
        />
      </div>
    </div>
  );
}

export default AdminBuiltInModelContent;
