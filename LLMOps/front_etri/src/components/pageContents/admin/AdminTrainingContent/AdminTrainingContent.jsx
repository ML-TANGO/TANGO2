import { useTranslation } from 'react-i18next';

import { ButtonV2, Selectbox } from '@tango/ui-react';

import FederatedLearningBtn from '@src/components/molecules/FederatedLearningBtn';
import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import Table from '@src/components/molecules/Table';

import AdminTrainingDetail from './AdminTrainingDetail';

import classNames from 'classnames/bind';
import style from './AdminTrainingContent.module.scss';

const cx = classNames.bind(style);

const IS_FL = import.meta.env.VITE_REACT_APP_IS_FEDERATED_LEARNING === 'true';

function AdminTrainingContent({
  columns,
  tableData,
  totalRows,
  searchKey,
  keyword,
  onSearchKeyChange,
  onSearch,
  onCreate,
  openDeleteConfirmPopup,
  trainingStatus,
  onStatusChange,
  trainingType,
  onTypeChange,
  onSelect,
  deleteBtnDisabled,
  toggledClearRows,
  moveJupyterLink,
  onJupyterControl,
  jobStop,
  onClear,
  handleRefresh,
  loading,
  onSortHandler,
}) {
  const { t } = useTranslation();

  const statusOptions = [
    { label: t('allStatus.label'), value: 'all' },
    { label: t('trainingRunning'), value: 'running' },
    { label: t('pending'), value: 'pending' },
    { label: t('stop'), value: 'stop' },
    { label: t('expired'), value: 'expired' },
  ];

  const typeOptions = [
    { label: t('allType.label'), value: 'all' },
    { label: 'Custom', value: 'advanced' },
    { label: 'Built-in', value: 'built-in' },
  ];

  const searchOptions = [
    { label: t('trainingName.label'), value: 'name' },
    { label: t('workspace.label'), value: 'workspace_name' },
    { label: t('owner.label'), value: 'user_name' },
    { label: t('user.label'), value: 'users' },
  ];

  const filterList = (
    <>
      {/* <RefreshButton onClick={onRefresh} /> */}
      <Selectbox
        size='medium'
        list={statusOptions}
        selectedItem={trainingStatus}
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
        list={typeOptions}
        selectedItem={trainingType}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={onTypeChange}
      /> */}
    </>
  );

  // const topButtonList = (
  //   <>
  //     <Button type='primary' onClick={onCreate}>
  //       {t('createTraining.label')}
  //     </Button>
  //   </>
  // );

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
    return (
      <AdminTrainingDetail
        data={row.data}
        moveJupyterLink={moveJupyterLink}
        onJupyterControl={onJupyterControl}
        jobStop={jobStop}
        tableData={tableData}
        getTrainingsData={handleRefresh}
      />
    );
  };

  return (
    <div id='AdminTrainingContent'>
      <PageHeader title={t('trainings.label')} />
      {IS_FL && (
        <div className={cx('fl-box')}>
          <FederatedLearningBtn />
        </div>
      )}
      <div className={cx('content', IS_FL && 'fl')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={totalRows}
          // topButtonList={topButtonList} 학습생성 버튼
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

export default AdminTrainingContent;
