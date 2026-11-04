import { Selectbox } from '@jonathan/ui-react';

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import Table from '@src/components/molecules/Table';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';

import classNames from 'classnames/bind';
import style from './ResourceTable.module.scss';

const cx = classNames.bind(style);

const ResourceTable = () => {
  const { t } = useTranslation();
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);

  const [keyword, setKeyword] = useState('');
  const [searchKey, setSearchKey] = useState({
    label: '',
    value: '',
  });
  const [loading, setLoading] = useState(false);
  const [spaceType, setSpaceType] = useState('storage'); // storage instance

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(6);

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('instanceName.label')}
          idx={0}
        />
      ),
      sortable: true,
      selector: '',
      minWidth: '300px',
      maxWidth: '400px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('workspace.use.label')}
          idx={1}
        />
      ),
      sortable: true,
      selector: '',
      minWidth: '300px',
      maxWidth: '400px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('recordTime.label')}
          idx={2}
        />
      ),
      sortable: true,
      selector: '',
      minWidth: '200px',
      maxWidth: '250px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('month.time.label')}
          idx={3}
        />
      ),
      sortable: true,
      selector: '',
      minWidth: '200px',
      maxWidth: '250px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('total.manage.fee.label')}
          idx={4}
        />
      ),
      sortable: true,
      selector: '',
      minWidth: '200px',
      maxWidth: '300px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('month.manage.fee.label')}
          idx={5}
        />
      ),
      sortable: true,
      selector: '',
      minWidth: '200px',
      maxWidth: '300px',
    },
  ];

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

  const tabComponent = (
    <div className={cx('tab')}>
      <div
        onClick={() => setSpaceType('storage')}
        className={cx('type', spaceType === 'storage' && 'selected')}
      >
        스토리지
      </div>
      <div
        onClick={() => setSpaceType('instance')}
        className={cx('type', spaceType === 'instance' && 'selected')}
      >
        인스턴스
      </div>
    </div>
  );

  const searchOptions = [];

  return (
    <div className={cx('container')}>
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
        // ExpandedComponent={ExpandedComponent}
        selectableRows={false}
        onSortHandler={onSortHandler}
      />
    </div>
  );
};

export default ResourceTable;
