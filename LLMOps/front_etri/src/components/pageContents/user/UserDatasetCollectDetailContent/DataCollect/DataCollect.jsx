import React, { useState } from 'react';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@tango/ui-react';

import SelectBox from '@src/components/atoms/SelectBox';
import Table from '@src/components/molecules/Table';
import TableEmptyBox from '@src/components/molecules/TableEmptyBox';

import {
  deleteCollectData,
  deleteCollectDataAll,
} from '@src/apis/flightbase/dataset/collect';
import { STATUS_SUCCESS } from '@src/network';

import useCollectList, { calColumn } from './useCollectList';

// CSS Module
import classNames from 'classnames/bind';
import style from './DataCollect.module.scss';

const cx = classNames.bind(style);

const calMessage = (status) => {
  if (!status || !status?.status)
    return {
      color: '#FA4E57',
      message: '데이터 수집을 실행하시려면, 실행 버튼을 클릭해 주세요.',
    };

  return {
    color: '#FF7A00',
    message: '데이터 수집 자원 설정 중입니다.',
  };
};

export default function DataCollect({
  status,
  collect_method,
  list,
  getHistoryList,
}) {
  const match = useRouteMatch();
  const { did: id } = match.params;

  const [selectedRow, setSelectedRow] = useState([]);
  const { color, message } = calMessage(status);

  const [clearSelected, setClearSelected] = useState(false);

  const {
    data: filterData,
    selectOptions,
    selectedValue,
    keyword,
    handleKeyword,
    handleKeywordReset,
    handleSelectOption,
  } = useCollectList(list, collect_method, getHistoryList);

  const columns = calColumn(collect_method);

  const handleDeleteBtn = async (selectRows) => {
    const list = selectRows.slice();
    if (list.length === 0) {
      toast.error('삭제하실 항목을 선택해 주세요.');
      return;
    }

    const idList = list.map((el) => el.id);
    const reqeusts = idList.map((historyId) =>
      deleteCollectData(id, historyId),
    );
    const response = await Promise.all(reqeusts);

    response.forEach(({ message, status }) => {
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      }
    });

    setSelectedRow([]);
    setClearSelected((prev) => !prev);
    await getHistoryList();
  };

  const handleAllDelete = async () => {
    if (selectedRow.length === 0) {
      toast.error('데이터가 존재하지 않습니다.');
      return;
    }

    await deleteCollectDataAll(id);
  };

  return (
    <div className={cx('modal')}>
      <Table
        loading={false}
        data={filterData}
        columns={columns}
        totalRows={filterData.length}
        bottomButtonList={
          <>
            <ButtonV2
              label='전체 삭제'
              colorType='lightRed'
              onClick={handleAllDelete}
            />
            <ButtonV2
              label='삭제'
              colorType='red'
              onClick={() => {
                handleDeleteBtn(selectedRow);
              }}
            />
          </>
        }
        filterList={
          <SelectBox
            value={selectedValue}
            list={selectOptions}
            handleOptionClick={handleSelectOption}
            style={{ width: '240px', height: '36px', backgroundColor: '#fff' }}
          />
        }
        onSelect={({ selectedRows }) => {
          setSelectedRow(selectedRows);
        }}
        toggledClearRows={clearSelected}
        onClear={handleKeywordReset}
        keyword={keyword}
        onSearch={handleKeyword}
        noDataComponent={<TableEmptyBox style={{ color }} message={message} />}
      />
    </div>
  );
}
