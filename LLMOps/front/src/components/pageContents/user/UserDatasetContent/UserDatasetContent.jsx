// i18n

// Components

// Icons

import { useTranslation } from 'react-i18next';

import { Button, ButtonV2, Selectbox } from '@jonathan/ui-react';

import PageTitle from '@src/components/atoms/PageTitle';
import DatasetCheckModalContainer from '@src/components/Modal/DatasetCheckModal/DatasetCheckModalContainer';
import Table from '@src/components/molecules/Table';

import classNames from 'classnames/bind';
// CSS module
import style from './UserDatasetContent.module.scss';

const cx = classNames.bind(style);

function UserDatasetContent({
  columns,
  tableData,
  totalRows,
  keyword,
  searchKey,
  onCreate,
  openDeleteConfirmPopup,
  onSearchKeyChange,
  onSearch,
  onSelect,
  onRowClick,
  deleteBtnDisabled,
  toggledClearRows,
  accessType,
  onAccessTypeChange,
  onAllSync,
  loading,
  onClear,
  builtInModalOpen,
  builtInModalOpenHandler,
  builtInModelList,
  builtInTemplateOpen,
  onClickDataResourceSetting,
  onSortHandler,
}) {
  const { t } = useTranslation();

  const accessTypeOptions = [
    { label: 'allAccessType.label', value: 'all' },
    { label: 'readAndWrite.label', value: 1 },
    { label: 'readOnly.label', value: 0 },
  ];

  const searchOptions = [
    { label: 'datasetName.label', value: 'dataset_name' },
    { label: 'creator.label', value: 'owner' },
  ];

  const filterList = (
    <div className={cx('btn-filter')}>
      {/* <Button
        type='primary-light'
        size='medium'
        onClick={onAllSync}
        iconAlign='left'
        icon={loading ? loadingIcon : syncIcon}
        customStyle={{ width: '100%' }}
      >
        {t('syncAll.label')}
      </Button> */}
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
        t={t}
      />
    </div>
  );

  const topButtonList = (
    <>
      {/* <Button type='primary' onClick={() => onCreate()}>
        {t('createDataset.label')}
      </Button> */}
      <div>
        {/* <Button
          type='primary-light'
          onClick={builtInModalOpenHandler}
          iconAlign='right'
          icon={
            builtInModalOpen
              ? '/images/icon/00-ic-basic-arrow-02-up-blue.svg'
              : '/images/icon/00-ic-basic-arrow-02-down-blue.svg'
          }
        >
          {t('builtInModelDataset.label')}
        </Button> */}
        <div className={cx('modal-wrap')}>
          {builtInModalOpen && (
            <DatasetCheckModalContainer
              list={builtInModelList}
              closeFunc={builtInModalOpenHandler}
              submit={{
                func: builtInTemplateOpen,
                text: t('openTemplate.label'),
              }}
            />
          )}
        </div>
      </div>
    </>
  );

  const bottomButtonList = (
    <>
      <button
        onClick={openDeleteConfirmPopup}
        className={cx('delete-btn', deleteBtnDisabled && 'disabled')}
        disabled={deleteBtnDisabled}
      >
        {t('delete.label')}
      </button>
    </>
  );

  return (
    <div id='UserDatasetContent' className={cx('wrapper')}>
      <div className={cx('page-header')}>
        <PageTitle>{t('datasetManagement.label')}</PageTitle>
        <div className={cx('btn')}>
          <ButtonV2
            colorType='skyblue'
            size='m'
            label={t('dataResourceManagementSettings.label')}
            disabled={true}
            onClick={() => onClickDataResourceSetting()}
          />
          <button
            className={cx('create-btn')}
            onClick={() => {
              onCreate();
            }}
          >
            {t('createDataset.label')}
          </button>
        </div>
      </div>
      {/* {IS_MARKER && MARKER_VERSION === '2' && (
        <div className={cx('marker-btn')}><NewMarkerBtn /></div>
      )} */}
      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={totalRows}
          topButtonList={topButtonList}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          onRowClick={onRowClick}
          onSelect={onSelect}
          defaultSortField='create_datetime'
          toggledClearRows={toggledClearRows}
          filterList={filterList}
          selectableRowDisabled={({ permission_level: permissionLevel }) =>
            permissionLevel > 3
          }
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

export default UserDatasetContent;
