import { ButtonV2, Selectbox } from '@jonathan/ui-react';

import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import Table from '@src/components/molecules/Table';

import { openModal } from '@src/store/modules/modal';

import AdminBasicBillingDetail from './AdminBasicBillingDetail';

import classNames from 'classnames/bind';
import style from './AdminBasicBillingContent.module.scss';

const cx = classNames.bind(style);

const timeUnit = {
  hour: '1시간당',
};

const AdminBasicBillingContent = ({
  basicInfo,
  columns,
  tableData,
  keyword,
  searchKey,
  loading,
  onSortHandler,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const openBasicFeeOptionModal = () => {
    dispatch(
      openModal({
        modalType: 'BASIC_FEE_OPTION',
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
      label={t('basicBillingOption')}
      size='l'
      colorType='skyblue'
      onClick={openBasicFeeOptionModal}
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
    return (row) => <AdminBasicBillingDetail data={row.data} />;
  }, []);

  return (
    <div>
      <PageHeader
        title={t('basicBillingManagement')}
        rightComponent={rightComponent}
      />
      <div className={cx('basic-container')}>
        <div className={cx('active-workspace')}>
          <span className={cx('title')}>{t('activeWorkspaceCount')}</span>
          <div className={cx('value')}>{basicInfo.activeWorkspace}</div>
        </div>
        <div className={cx('pay-info')}>
          <div className={cx('basic-pay')}>
            <span className={cx('title')}>{t('workspaceBasicPay')}</span>
            <div className={cx('value')}>
              {timeUnit[basicInfo.timeUnit]}&nbsp;
              {basicInfo.workspaceBasicFee.toLocaleString()} 원
            </div>
          </div>
          <div className={cx('divider')}></div>
          <div className={cx('add-pay')}>
            <div className={cx('title')}>
              <span className={cx('main')}>{t('memberSurcharge')}</span>
              <span className={cx('sub')}>
                {t('basicMemberCount')}&nbsp;
                <span className={cx('count')}>{basicInfo.member} 명</span>
              </span>
            </div>
            <div className={cx('value')}>
              {basicInfo.addMemberCost.toLocaleString()} 원
            </div>
          </div>
        </div>
        <div className={cx('network-pay')}>
          <span className={cx('title')}>{t('outbounceNetworkPay')}</span>
          <div className={cx('detail')}>
            <span className={cx('text')}>{t('trafficSection')}</span>
            {basicInfo.outBoundNetwork.map(
              ({ start, start_unit, end, end_unit, cost }, index) => {
                return (
                  <div key={index} className={cx('info')}>
                    <span>
                      {start} {start_unit} 이상 {end} {end_unit} 미만
                    </span>
                    <span className={cx('cost')}>
                      {cost.toLocaleString()} 원
                    </span>
                  </div>
                );
              },
            )}
          </div>
        </div>
      </div>
      <div className={cx('middle-gray-bar')}></div>
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
        selectableRows={false}
        onSortHandler={onSortHandler}
      />
    </div>
  );
};

export default AdminBasicBillingContent;
