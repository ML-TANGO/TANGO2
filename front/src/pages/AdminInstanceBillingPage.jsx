import { Switch } from '@jonathan/ui-react';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import AdminInstanceBillingContent from '@src/components/pageContents/admin/AdminInstanceBilling/AdminInstanceBillingContent';

import { callApi, STATUS_SUCCESS } from '@src/network';

const timeUnit = {
  hour: '시간당',
  minute: '분당',
  day: '일',
  month: '월',
};

const AdminInstanceBillingPage = () => {
  const { t } = useTranslation();

  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [searchKey, setSearchKey] = useState({
    label: '',
    value: '',
  });
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [chargeType, setChargeType] = useState('payYou');

  const columns = [
    {
      name: t('packageName'),
      sortable: true,
      selector: (row) => row.name,
      minWidth: '500px',
      maxWidth: '700px',
    },
    {
      name: t('payPolicy'),
      minWidth: '300px',
      maxWidth: '400px',
      sortable: true,
      cell: ({ time_unit, time_unit_cost }) => {
        return `${timeUnit[time_unit]} ${time_unit_cost}원`;
      },
    },
    {
      name: t('activation.label'),
      minWidth: '300px',
      maxWidth: '400px',
      cell: ({ active, id }) => {
        return (
          <Switch
            // disabled={}
            // message={'hi'}
            // customStyle={switchBackgroundColor}
            size='large'
            checked={active === 1}
            onChange={() => {
              updateInstanceActive(id, active);
            }}
          />
        );
      },
    },
    {
      name: t('edit.label'),
      maxWidth: '64px',
      cell: ({ id }) => (
        <img
          // style={{
          //   opacity: row.status === 2 && row.type !== 0 ? 1 : 0.2,
          // }}
          className='table-icon'
          src='/images/icon/00-ic-basic-pen.svg'
          alt='edit'
          onClick={() => {
            // if (row.status === 2 && row.type !== 0) onUpdate(row);
          }}
        />
      ),
      button: true,
    },
  ];

  const updateInstanceActive = async (id, active) => {
    const response = await callApi({
      url: `cost-management/instance-package-active`,
      method: 'post',
      body: {
        id,
        active: active === 0 ? true : false,
      },
    });

    const { status } = response;

    if (status === STATUS_SUCCESS) {
      getInstancePay();
    }
  };

  const getInstancePay = async () => {
    const response = await callApi({
      url: 'cost-management/instance-package',
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      setOriginData(result);
      setTableData(result);
    }
  };

  useEffect(() => {
    getInstancePay();
  }, []);

  return (
    <AdminInstanceBillingContent
      keyword={keyword}
      searchKey={searchKey}
      loading={loading}
      chargeType={chargeType}
      setChargeType={setChargeType}
      columns={columns}
      tableData={tableData}
    />
  );
};

export default AdminInstanceBillingPage;
