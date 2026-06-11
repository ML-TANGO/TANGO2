import { ButtonV2, Selectbox } from '@tango/ui-react';

import { useTranslation } from 'react-i18next';

import PageTitle from '@src/components/atoms/PageTitle';
import Table from '@src/components/molecules/Table';

import AdminGroupDetail from './AdminGroupDetail';
import AdminUserDetail from './AdminUserDetail';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminUserContent.module.scss';

const cx = classNames.bind(style);

function AdminUserContent({
  columns,
  tableData,
  totalRows,
  searchKey,
  keyword,
  onSearchKeyChange,
  onSearch,
  onCreate,
  openDeleteConfirmPopup,
  userType,
  onTypeChange,
  onSelect,
  deleteBtnDisabled,
  toggledClearRows,
  moreList,
  tabHandler,
  tab,
  onClear,
  onSortHandler,
  onUserGroupRefresh,
  onUserRefresh,
}) {
  const { t } = useTranslation();

  const typeOptions = [
    { label: t('allUserType.label'), value: 'all' },
    { label: t('admin.label'), value: 0 },
    { label: t('workspaceManager.label'), value: 1 },
    { label: t('trainingOwner.label'), value: 2 },
    { label: t('user.label'), value: 3 },
  ];

  const searchOptions = [{ label: t('userID.label'), value: 'name' }];
  const groupSearchOptions = [{ label: t('groupName.label'), value: 'name' }];
  const filterList = (
    <Selectbox
      size='medium'
      list={typeOptions}
      selectedItem={userType}
      customStyle={{
        selectboxForm: {
          width: '184px',
        },
        listForm: {
          width: '184px',
        },
      }}
      onChange={onTypeChange}
    />
  );

  const bottomButtonList = (
    <ButtonV2
      size='l'
      label={t('delete.label')}
      colorType='lightRed'
      onClick={openDeleteConfirmPopup}
      disabled={deleteBtnDisabled}
    />
  );

  const ExpandedComponent = (row) => {
    const {
      data: { register },
    } = row;

    if (register) {
      return '';
    }

    return tab.value === 0 ? (
      <AdminUserDetail data={row.data} moreList={moreList} />
    ) : (
      <AdminGroupDetail
        data={row.data}
        description={row.data.description}
        name={row.data.name}
        userNameList={row.data.user_name_list}
      />
    );
  };

  const navList = [
    { label: 'user', value: 0 },
    { label: 'userGroup', value: 1 },
  ];

  return (
    <div className={cx('content')}>
      <PageTitle style={{ marginBottom: '24px' }}>{t('users.label')}</PageTitle>
      <div className={cx('tab')}>
        <ul className={cx('tab-list')}>
          <div className={cx('flex-cont')}>
            {navList.map(({ label, value }, idx) => (
              <li
                className={cx('tab-item')}
                key={idx}
                onClick={() => tabHandler({ value })}
              >
                <div className={cx('cont', value === tab.value && 'active')}>
                  <span className={cx('link-name')}>{t(label)}</span>
                  <span className={cx('stick')}></span>
                </div>
              </li>
            ))}
          </div>
          <ButtonV2
            colorType='white'
            label={tab.value === 0 ? t('addUser.label') : t('addGroup.label')}
            onClick={onCreate}
          />
        </ul>
      </div>
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
        selectableRowDisabled={({ name, register }) => {
          return name === 'admin' || register; // admin과 register는 선택 x
        }}
        filterList={tab.value === 0 && filterList}
        searchOptions={tab.value === 0 ? searchOptions : groupSearchOptions}
        searchKey={searchKey}
        keyword={keyword}
        onSearchKeyChange={onSearchKeyChange}
        onSearch={(e) => {
          onSearch(e.target.value);
        }}
        onClear={onClear}
        onSortHandler={onSortHandler}
        handleRefresh={tab.value === 0 ? onUserRefresh : onUserGroupRefresh}
      />
    </div>
  );
}

export default AdminUserContent;
