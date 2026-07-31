// Components
import { ButtonV2, Selectbox } from '@tango/ui-react';

import { useMemo } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import AdminPageHeader from '@src/components/molecules/AdminPageHeader/AdminPageHeader';
import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import Table from '@src/components/molecules/Table';

import AdminDockerImageDetail from './AdminDockerImageDetail';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDockerImageContent.module.scss';

const cx = classNames.bind(style);

const uploadTypeOptions = [
  { label: 'allCreateType.label', value: 'all' },
  { label: 'Built-in', value: 0 },
  { label: 'Pull', value: 1 },
  { label: 'Tar', value: 2 },
  { label: 'Dockerfile Build', value: 3 },
  { label: 'Tag', value: 4 },
  { label: 'NGC', value: 5 },
  { label: 'Commit', value: 6 },
];

const releaseTypeOptions = [
  { label: 'allReleaseType.label', value: 'all' },
  { label: 'workspace.label', value: 0 },
  { label: 'global.label', value: 1 },
];

const searchOptions = [
  { label: 'dockerImageName.label', value: 'image_name' },
  { label: 'workspace.label', value: 'workspace_name' },
  { label: 'creator.label', value: 'user_name' },
];

function AdminDockerImageContent({
  columns,
  tableData,
  totalRows,
  searchKey,
  onSearchKeyChange,
  keyword,
  onSearch,
  onSelect,
  onClear,
  toggledClearRows,
  onCreate,
  deleteBtnDisabled,
  openDeleteConfirmPopup,
  uploadType,
  onUploadTypeChange,
  releaseType,
  onReleaseTypeChange,
  onSortHandler,
  getImages,
}) {
  const { t } = useTranslation();

  const filterList = (
    <>
      <Selectbox
        size='medium'
        list={uploadTypeOptions}
        selectedItem={uploadType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onUploadTypeChange}
        t={t}
      />
      <Selectbox
        size='medium'
        list={releaseTypeOptions}
        selectedItem={releaseType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onReleaseTypeChange}
        t={t}
      />
      {/* <RefreshButton onClick={getImages} /> */}
    </>
  );

  const rightComponent = (
    <ButtonV2
      label={t('createDockerImage.label')}
      size='l'
      // colorType='white'
      onClick={onCreate}
    />
  );

  const bottomButtonList = (
    <>
      <ButtonV2
        colorType='lightRed'
        size='l'
        onClick={openDeleteConfirmPopup}
        disabled={deleteBtnDisabled}
      >
        {t('delete.label')}
      </ButtonV2>
    </>
  );

  const ExpandedComponent = useMemo(() => {
    return (row) => <AdminDockerImageDetail data={row.data} />;
  }, []);

  return (
    <div id='AdminDockerImageContent'>
      <AdminPageHeader
        sectionTitle={'작업 환경 관리'}
        title={t('dockerImages.label')}
        rightComponent={rightComponent}
      />

      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={totalRows}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          ExpandedComponent={ExpandedComponent}
          onSelect={onSelect}
          onClear={onClear}
          defaultSortField='create_datetime'
          toggledClearRows={toggledClearRows}
          selectableRowDisabled={({ type, status }) =>
            type === 0 || status === 0 || status === 1 || status === 4
          }
          filterList={filterList}
          searchOptions={searchOptions}
          searchKey={searchKey}
          keyword={keyword}
          onSearchKeyChange={onSearchKeyChange}
          onSearch={(e) => {
            onSearch(e.target.value);
          }}
          onSortHandler={onSortHandler}
          isRefreshBtn
          handleRefresh={() => getImages()}
        />
      </div>
    </div>
  );
}

export default AdminDockerImageContent;
