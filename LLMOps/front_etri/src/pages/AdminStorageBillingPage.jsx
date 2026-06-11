import { Switch } from '@tango/ui-react';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import AdminStorageBillingContent from '@src/components/pageContents/admin/AdminStorageBilling/AdminStorageBillingContent';

import { callApi, STATUS_SUCCESS } from '@src/network';

const AdminStorageBillingPage = () => {
  const { t } = useTranslation();

  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [searchKey, setSearchKey] = useState({
    label: '',
    value: '',
  });
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);

  const updateInstanceActive = async (id, active) => {
    const response = await callApi({
      url: `cost-management/storage-package-active`,
      method: 'post',
      body: {
        id,
        active: active === 0 ? true : false,
      },
    });

    const { status } = response;

    if (status === STATUS_SUCCESS) {
      getStoragePay();
    }
  };

  const columns = [
    {
      name: t('packageName'),
      sortable: true,
      selector: (row) => row.name,
      minWidth: '200px',
      maxWidth: '300px',
    },
    {
      name: `${t('deploymentInputPackage.placeholder')} ${t(
        'configuration.label',
      )}`,
      sortable: true,
      selector: (row) => '임시 패키지',
      minWidth: '200px',
      maxWidth: '300px',
    },
    {
      name: t('data.size.label'),
      minWidth: '200px',
      maxWidth: '300px',
      cell: ({ size, size_unit }) => {
        return `${size} ${size_unit}`;
      },
    },
    {
      name: t('payPolicy'),
      minWidth: '200px',
      maxWidth: '300px',
      selector: (row) => row.cost,
      cell: ({ cost }) => {
        return `${cost.toLocaleString()} 원`;
      },
    },
    {
      name: t('source.label'),
      minWidth: '200px',
      maxWidth: '300px',
      selector: (row) => row.source,
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

  const getStoragePay = async () => {
    const response = await callApi({
      url: 'cost-management/storage-package',
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      setOriginData(result);
      setTableData(result);
    }
  };

  useEffect(() => {
    getStoragePay();
  }, []);

  return (
    <AdminStorageBillingContent
      keyword={keyword}
      searchKey={searchKey}
      loading={loading}
      columns={columns}
      tableData={tableData}
    />
  );
};

export default AdminStorageBillingPage;
