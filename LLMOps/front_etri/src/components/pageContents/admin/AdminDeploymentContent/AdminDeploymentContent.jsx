// i18n

// Components
import { Button, ButtonV2, Selectbox } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import PageTitle from '@src/components/atoms/PageTitle';
import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import RefreshButton from '@src/components/molecules/RefreshButton';
import Table from '@src/components/molecules/Table';

import AdminDeploymentDetail from './AdminDeploymentDetail';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDeploymentContent.module.scss';

const cx = classNames.bind(style);

function AdminDeploymentContent({
  columns,
  tableData,
  totalRows,
  searchKey,
  keyword,
  onSearchKeyChange,
  onSearch,
  onCreate,
  openDeleteConfirmPopup,
  deploymentStatus,
  onStatusChange,
  deploymentType,
  onDeploymentTypeChange,
  onSelect,
  deleteBtnDisabled,
  toggledClearRows,
  onClear,
  handleRefresh,
  loading,
  onSortHandler,
}) {
  const { t } = useTranslation();

  const statusOptions = [
    { label: t('allStatus.label'), value: 'all' },
    { label: t('deploymentRunning'), value: 'running' },
    { label: t('installing'), value: 'installing' },
    { label: t('stop'), value: 'stop' },
    { label: t('error'), value: 'error' },
  ];

  // const deploymentTypeOptions = [
  //   { label: 'allModelType.label', value: 'all' },
  //   { label: 'Built-in', value: 'built-in' },
  //   { label: 'Custom', value: 'custom' },
  // ];

  const searchOptions = [
    { label: 'deploymentName.label', value: 'deployment_name' },
    { label: 'workspace.label', value: 'workspace_name' },
    { label: 'owner.label', value: 'user_name' },
    { label: 'user.label', value: 'users' },
  ];

  const filterList = (
    <>
      {/* <RefreshButton onClick={handleRefresh} /> */}
      <Selectbox
        size='medium'
        list={statusOptions}
        selectedItem={deploymentStatus}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onStatusChange}
      />
      {/* <Selectbox
        size='medium'
        list={deploymentTypeOptions}
        selectedItem={deploymentType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
        }}
        onChange={onDeploymentTypeChange}
        t={t}
      /> */}
    </>
  );

  const topButtonList = (
    <>
      <Button type='primary' onClick={onCreate}>
        {t('createDeployment.label')}
      </Button>
    </>
  );

  const bottomButtonList = (
    <>
      <ButtonV2
        label={t('delete.label')}
        size='l'
        colorType='lightRed'
        onClick={openDeleteConfirmPopup}
        disabled={deleteBtnDisabled}
      />
    </>
  );

  const ExpandedComponent = (row) => {
    return <AdminDeploymentDetail data={row.data} onRefresh={handleRefresh} />;
  };

  return (
    <div id='AdminDeploymentContent'>
      <PageHeader title={t('deployments.label')} />
      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={totalRows}
          // topButtonList={topButtonList}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          ExpandedComponent={ExpandedComponent}
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
          loading={loading}
          onSortHandler={onSortHandler}
          isRefreshBtn
          handleRefresh={handleRefresh}
        />
      </div>
    </div>
  );
}

export default AdminDeploymentContent;
