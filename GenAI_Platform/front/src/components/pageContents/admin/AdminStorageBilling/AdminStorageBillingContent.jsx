import { ButtonV2, Selectbox } from '@jonathan/ui-react';

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import Table from '@src/components/molecules/Table';

import { openModal } from '@src/store/modules/modal';

import StorageBillingDetail from './StorageBillingDetail';

import classNames from 'classnames/bind';
import style from './AdminStorageBillingContent.module.scss';

const cx = classNames.bind(style);

const AdminStorageBillingContent = ({
  keyword,
  searchKey,
  loading,
  columns,
  tableData,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const openPackageModal = () => {
    dispatch(
      openModal({
        modalType: 'BILLING_STORAGE_PACKAGE',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {},
          },
          cancel: {
            text: 'cancel.label',
          },
        },
      }),
    );
  };

  const rightComponent = (
    <ButtonV2
      label={t('createChargePackage')}
      size='l'
      colorType='skyblue'
      onClick={openPackageModal}
    />
  );

  const filterList = (
    <>
      <Selectbox
        size='medium'
        list={[]}
        selectedItem={{
          label: '',
          value: '',
        }}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={() => {}}
        t={t}
      />
      <Selectbox
        size='medium'
        list={[]}
        selectedItem={{
          label: '',
          value: '',
        }}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={() => {}}
        t={t}
      />
    </>
  );

  const searchOptions = [];

  const ExpandedComponent = useMemo(() => {
    return (row) => <StorageBillingDetail data={row.data} />;
  }, []);

  return (
    <div id='AdminDeploymentContent'>
      <PageHeader
        title={t('storageBillingManagement')}
        desc={t('storage.package.desc')}
        rightComponent={rightComponent}
      />
      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          filterList={filterList}
          searchOptions={searchOptions}
          keyword={keyword}
          searchKey={searchKey}
          onSearch={(e) => {
            // onSearch(e.target.value);
          }}
          loading={loading}
          ExpandedComponent={ExpandedComponent}
        />
      </div>
    </div>
  );
};

export default AdminStorageBillingContent;
