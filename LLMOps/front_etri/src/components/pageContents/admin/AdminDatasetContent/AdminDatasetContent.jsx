// i18n

// Components
import { ButtonV2, Selectbox } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import Table from '@src/components/molecules/Table';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDatasetContent.module.scss';

const cx = classNames.bind(style);

function AdminDatasetContent({
  columns,
  tableData,
  tableLoading,
  totalRows,
  searchKey,
  keyword,
  onSearchKeyChange,
  onSearch,
  onCreate,
  openDeleteConfirmPopup,
  onSelect,
  deleteBtnDisabled,
  toggledClearRows,
  accessType,
  onAccessTypeChange,
  onClear,
  onSortHandler,
  onChangeRowsPerPage,
  handleRefresh,
}) {
  const { t } = useTranslation();

  const accessTypeOptions = [
    { label: t('allAccessType.label'), value: 'all' },
    { label: t('readAndWrite.label'), value: 1 },
    { label: t('readOnly.label'), value: 0 },
  ];

  const searchOptions = [
    { label: t('datasetName.label'), value: 'dataset_name' },
    { label: t('workspace.label'), value: 'workspace_name' },
    { label: t('creator.label'), value: 'owner' },
  ];

  const filterList = (
    <div className={cx('btn-filter')}>
      <Selectbox
        size='medium'
        list={accessTypeOptions}
        selectedItem={accessType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onAccessTypeChange}
      />
    </div>
  );

  // const topButtonList = (
  //   <>
  //     <Button type='primary' onClick={onCreate}>
  //       {t('createDataset.label')}
  //     </Button>
  //   </>
  // );

  const bottomButtonList = (
    <ButtonV2
      size='l'
      label={t('delete.label')}
      colorType='lightRed'
      onClick={openDeleteConfirmPopup}
      disabled={deleteBtnDisabled}
    />
  );

  return (
    <div id='AdminDatasetContent'>
      <PageHeader title={t('datasets.label')} />
      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          loading={tableLoading}
          totalRows={totalRows}
          // topButtonList={topButtonList}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          // onRowClick={onRowClick}
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
          onChangeRowsPerPage={onChangeRowsPerPage}
          onClear={onClear}
          onSortHandler={onSortHandler}
          handleRefresh={handleRefresh}
        />
      </div>
    </div>
  );
}

export default AdminDatasetContent;
