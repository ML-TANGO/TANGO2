import { ButtonV2, Selectbox } from '@tango/ui-react';

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import Table from '@src/components/molecules/Table';

import { openModal } from '@src/store/modules/modal';

import AdminInstanceBillingDetail from './AdminInstanceBillingDetail';

import classNames from 'classnames/bind';
import style from './AdminInstanceBillingContent.module.scss';

const cx = classNames.bind(style);

const AdminInstanceBillingContent = ({
  keyword,
  searchKey,
  loading,
  chargeType,
  setChargeType,
  columns,
  tableData,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const openPackageModal = () => {
    dispatch(
      openModal({
        modalType: 'BILLING_PACKAGE',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {},
          },
          cancel: {
            text: 'cancel.label',
          },
          chargeType,
        },
      }),
    );
  };

  const tabComponent = (
    <div className={cx('tab')}>
      <div
        onClick={() => setChargeType('payYou')}
        className={cx('type', chargeType === 'payYou' && 'selected')}
      >
        종량제
      </div>
      <div
        onClick={() => setChargeType('subscribe')}
        className={cx('type', chargeType === 'subscribe' && 'selected')}
      >
        구독제
      </div>
    </div>
  );

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
    return (row) => <AdminInstanceBillingDetail data={row.data} />;
  }, []);

  return (
    <div id='AdminInstanceBillingContent'>
      <PageHeader
        title={t('instanceBillingManagement')}
        desc={t('instance.package.desc')}
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
          tabComponent={tabComponent}
          ExpandedComponent={ExpandedComponent}
        />
      </div>
    </div>
  );
};

export default AdminInstanceBillingContent;
