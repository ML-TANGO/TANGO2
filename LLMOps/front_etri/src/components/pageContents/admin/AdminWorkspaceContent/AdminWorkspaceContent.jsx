// i18n

// Components
import { Button, ButtonV2, Selectbox } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import PageTitle from '@src/components/atoms/PageTitle';
import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import RefreshButton from '@src/components/molecules/RefreshButton';
import Table from '@src/components/molecules/Table';

import AdminWorkspaceDetail from './AdminWorkspaceDetail';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminWorkspaceContent.module.scss';

const cx = classNames.bind(style);

function AdminWorkspaceContent({
  columns,
  tableData,
  totalRows,
  searchKey,
  keyword,
  onSearchKeyChange,
  onSearch,
  onCreate,
  openDeleteConfirmPopup,
  workspaceStatus,
  onStatusChange,
  onSelect,
  deleteBtnDisabled,
  toggledClearRows,
  moreList,
  onClear,
  onSortHandler,
  handleRefresh,
}) {
  const { t } = useTranslation();

  const statusOptions = [
    { label: t('allStatus.label'), value: 'all' },
    { label: t('active'), value: 'active' },
    { label: t('reserved'), value: 'reserved' },
    { label: t('expired'), value: 'expired' },
  ];

  const searchOptions = [
    { label: t('workspaceName.label'), value: 'name' },
    { label: t('workspaceManager.label'), value: 'manager' },
    { label: t('user.label'), value: 'user' },
  ];

  const filterList = (
    <>
      <Selectbox
        size='medium'
        list={statusOptions}
        selectedItem={workspaceStatus}
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
    </>
  );

  const bottomButtonList = (
    <>
      <ButtonV2
        size='l'
        label={t('delete.label')}
        colorType='lightRed'
        onClick={openDeleteConfirmPopup}
        disabled={deleteBtnDisabled}
      />
    </>
  );

  const ExpandedComponent = (row) => {
    return <AdminWorkspaceDetail data={row.data} moreList={moreList} />;
  };

  const rightComponent = (
    <ButtonV2
      label={t('createWorkspace.label')}
      size='l'
      colorType='white'
      onClick={onCreate}
    />
  );

  return (
    <div id='AdminWorkspaceContent'>
      <PageHeader
        title={t('workspaces.label')}
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
          selectableRowDisabled={({ isCheckDisabled }) => isCheckDisabled}
          isRefreshBtn
          handleRefresh={handleRefresh}
        />
      </div>
    </div>
  );
}

export default AdminWorkspaceContent;
