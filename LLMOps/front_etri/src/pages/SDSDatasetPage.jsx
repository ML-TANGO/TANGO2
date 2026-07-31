import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import PageTitle from '@src/components/atoms/PageTitle';
import Table from '@src/components/molecules/Table';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import { startPath } from '@src/store/modules/breadCrumb';
import { closeConfirm, openConfirm } from '@src/store/modules/confirm';
import { convertBinaryByte } from '@src/utils';

import classNames from 'classnames/bind';
import style from './SDSDatasetPage.module.scss';

const cx = classNames.bind(style);

// Mock data populated with the actual files/directories under /home/etri/TANGO2/Field_Test/SDS/dataset/20260227
const MOCK_FILES = [
  { name: 'README.md', size: 2648, type: 'Markdown File', date: '2026-02-27' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-0dL1k060Ox', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-0dLhkqLMw', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-0dzraEavMx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-0p0rtLzOH', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-0pvAkDzMx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-H-FMrdbSdY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-H-F_rRP2ZY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-H-LCr1yoZY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-H-i0H5CZb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-H-iCrVyEZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-H-q0xT_mP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHF0HRj_mY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHF0xWgSmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHFC-EdY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHFCrI7SdP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHFCrMjEmP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHLCHmjMdP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHi0xdoZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHqC-Q5omb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHqM-pCdb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHq_-Wy0eV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HHq_HNyMmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HrLC-wOCmP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-Hri_r72eY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HxL0Hzj_ZY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-Hxi0xXgCZY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HxiC-rg2ZP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-Hxq0xjgSmb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-HxqCxMMdP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-LCLAkPzMx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-LCzraxa0I7', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-LWLAaO6zB7', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-LWLr6R6vBH', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-Ld01aGzOw', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-Lp0rka0Ow', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-r-FMxiySZb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-r-LMr6MdV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-r-i0-dCdP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-r-i0-kEmV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-r-qMraEdY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-r-q_-6jCZb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rHF0-MYoeV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rHF0rCg_dY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rHiCrRMZY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rHqCxUhMmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrFCxT7SdP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrL0-ESeb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrL0xHSZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rriCrV0Zb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrq0rXhEZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrqCrpy2ZP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrq_-7VEmb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rrq_ruhSeY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxF0-tKSmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxFMrOhCeV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxF_xHVSmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxL0HiPEmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxLMx2KomY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxL_rqgCmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxiCxTh0db', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxi_xv2ZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxq0xF_eb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-rxqM-f2mb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vC0AaMzMx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vCzr65vIx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vW016W6LBx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vd01arvI7', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vdLA60Bx', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vpLhasvOH', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-vpz1aVvB7', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-FCHX7SdP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-L0rg0eV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-LMHUYSmV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-LMrwgodY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-iCr17EdY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-iCxfjEmY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-x-q_HMZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xHL0rLEmb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xHLC-KyomP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xHLM-rh0db', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xHqCxgg_eP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xrLM-P5EZY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xrL_HbK_ZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xrq0HzbEmV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xrq0rboZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xrq_-kPoZV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xrq_HBhoZb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxFCxogMeY', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxL0HxMZb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxiCxM7oZb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxiCxqOomb', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxi_-x50ZP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxi_xoyEdV', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-xxqMxOKEmP', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-zCzh6o0O7', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-zW01axLOw', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-zWL16t60Bw', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-zWLh6_LI7', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-zWzAtqkLOH', size: 1582740, type: 'Directory', date: '2026-02-26' },
  { name: 'tango_sds-unity-llm-20260226-v0.3-zdvAaKvBw', size: 1582740, type: 'Directory', date: '2026-02-26' }
].map((item, idx) => ({ id: idx + 1, ...item }));

function SDSDatasetPage() {
  const dispatch = useDispatch();
  const { t } = useTranslation();

  const [originData, setOriginData] = useState(MOCK_FILES);
  const [tableData, setTableData] = useState(MOCK_FILES);
  const [keyword, setKeyword] = useState('');
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);

  const searchOptions = [
    { label: t('fileName.label', 'File Name'), value: 'name' },
    { label: t('type.label', 'Type'), value: 'type' },
  ];

  const [searchKey, setSearchKey] = useState(searchOptions[0]);

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(4);

  const onSearch = useCallback(
    (value) => {
      let filteredData = originData;
      if (value !== '') {
        filteredData = filteredData.filter((item) =>
          item[searchKey.value].toLowerCase().includes(value.toLowerCase())
        );
      }
      setKeyword(value);
      setTableData(filteredData);
    },
    [originData, searchKey.value]
  );

  const onClear = () => {
    setKeyword('');
    setTableData(originData);
  };

  const onSelect = ({ selectedRows }) => {
    setSelectedRows(selectedRows);
  };

  const onDelete = () => {
    const ids = selectedRows.map(({ id }) => id);
    const newOrigin = originData.filter((item) => !ids.includes(item.id));
    setOriginData(newOrigin);
    setSelectedRows([]);
    setToggledClearRows(!toggledClearRows);
    alert('Mock Delete: Files successfully removed from local UI list.');
    dispatch(closeConfirm());
  };

  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteDatasetPopup.title.label',
        content: 'deleteDatasetPopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
          },
        },
        cancel: {
          text: 'cancel.label',
          func: () => {
            dispatch(closeConfirm());
          },
        },
      })
    );
  };

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const breadCrumbHandler = () => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Dataset',
            t,
          },
        },
        {
          component: {
            name: 'SDS Dataset',
            t,
          },
        },
      ])
    );
  };

  useEffect(() => {
    breadCrumbHandler();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey, originData]);

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('fileName.label', 'File Name')}
          idx={0}
        />
      ),
      selector: 'name',
      sortable: true,
      minWidth: '250px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('size.label', 'Size')}
          idx={1}
        />
      ),
      selector: 'size',
      sortable: true,
      maxWidth: '150px',
      cell: ({ size }) => {
        if (typeof size === 'number') {
          return convertBinaryByte(size);
        }
        return size;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('type.label', 'Type')}
          idx={2}
        />
      ),
      selector: 'type',
      sortable: true,
      maxWidth: '150px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('date.label', 'Date')}
          idx={3}
        />
      ),
      selector: 'date',
      sortable: true,
      maxWidth: '150px',
    },
  ];

  const bottomButtonList = (
    <>
      <button
        onClick={openDeleteConfirmPopup}
        className={cx('delete-btn', selectedRows.length === 0 && 'disabled')}
        disabled={selectedRows.length === 0}
      >
        {t('delete.label', 'Delete')}
      </button>
    </>
  );

  return (
    <div id="SDSDatasetContent" className={cx('wrapper')}>
      <div className={cx('page-header')}>
        <PageTitle>SDS Dataset</PageTitle>
        <div className={cx('btn')}>
          <button
            className={cx('create-btn')}
            onClick={() => {
              alert('Mock Upload: File uploading triggered.');
            }}
          >
            Upload
          </button>
        </div>
      </div>
      <div className={cx('content')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={tableData.length}
          bottomButtonList={tableData.length > 0 && bottomButtonList}
          onSelect={onSelect}
          defaultSortField="name"
          toggledClearRows={toggledClearRows}
          searchOptions={searchOptions}
          searchKey={searchKey}
          keyword={keyword}
          onSearchKeyChange={(value) => setSearchKey(value)}
          onSearch={(e) => {
            onSearch(e.target.value);
          }}
          onClear={onClear}
          onSortHandler={onSortHandler}
        />
      </div>
    </div>
  );
}

export default SDSDatasetPage;
