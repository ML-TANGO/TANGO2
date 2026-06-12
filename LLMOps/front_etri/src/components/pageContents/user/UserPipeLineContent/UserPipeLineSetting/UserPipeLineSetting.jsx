// CSS Module
import { useCallback, useEffect, useState } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { Badge } from '@tango/ui-react';

import SortColumn from '@src/components/molecules/BorderTable/TableHead/SortColumn';
import Table from '@src/components/molecules/Table';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';

import { getPipelineHistoryApi } from '@src/apis/flightbase/pipeline';
import { STATUS_SUCCESS } from '@src/network';

import { calPlusNineHours, calRecordTime, convertBinaryByte } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserPipeLineSetting.module.scss';

const cx = classNames.bind(style);

const getPipelineHistory = async (pipeline_id, setPipelineHistory) => {
  const { result, message, status } = await getPipelineHistoryApi(pipeline_id);

  if (status === STATUS_SUCCESS) {
    setPipelineHistory(result);
  } else {
    toast.error(message);
  }
};

export default function UserPipeLineSetting() {
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId, tid: pipelineId } = match.params;

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(7);

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'자동 업데이트 설정'}
          idx={0}
        />
      ),
      selector: 'is_retraining_setting',
      sortable: true,
      center: true,
      minWidth: '160px',
      maxWidth: '160px',
      cell: ({ is_retraining_setting }) => {
        const label = is_retraining_setting ? '설정' : '미설정';
        const color = is_retraining_setting ? 'primary-2' : 'gray';
        return <Badge label={label} type={color} size='lg'></Badge>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'시작 시간'}
          idx={1}
        />
      ),
      selector: 'start_datetime',
      sortable: true,
      minWidth: '252px',
      maxWidth: '252px',
      center: true,
      cell: ({ start_datetime }) => {
        return <>{calPlusNineHours(start_datetime)}</>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'종료 시간'}
          idx={2}
        />
      ),
      selector: 'end_datetime',
      sortable: true,
      center: true,
      minWidth: '252px',
      maxWidth: '252px',
      cell: ({ end_datetime }) => {
        return <>{calPlusNineHours(end_datetime) ?? '-'}</>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'재학습 횟수'}
          idx={3}
        />
      ),
      selector: 'retraining_count',
      sortable: true,
      minWidth: '120px',
      maxWidth: '120px',
      center: true,
      cell: ({ retraining_count }) => {
        return <>{retraining_count} 회</>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'데이터 증가량'}
          idx={4}
        />
      ),
      selector: 'increase_dataset_size',
      sortable: true,
      center: true,
      minWidth: '140px',
      maxWidth: '140px',
      cell: ({ increase_dataset_size }) => {
        return <>{convertBinaryByte(increase_dataset_size)}</>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'실행 현황'}
          idx={5}
        />
      ),
      selector: 'end_status',
      sortable: true,
      center: true,
      minWidth: '120px',
      maxWidth: '120px',
      cell: ({ end_status }) => {
        return <>{end_status ?? '-'}</>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'실행자'}
          idx={6}
        />
      ),
      selector: 'start_user_name',
      sortable: true,
      center: true,
      grow: 160,
      cell: ({ start_user_name }) => {
        return <>{start_user_name}</>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={'소요 시간'}
          idx={7}
        />
      ),
      selector: 'start_datetime',
      sortable: true,
      center: true,
      minWidth: '252px',
      cell: ({ start_datetime, end_datetime }) => {
        const diffTime = calRecordTime(start_datetime, end_datetime);
        return <>{diffTime}</>;
      },
    },
  ];

  const handleRowClick = useCallback(
    (info) => {
      const { id } = info;
      history.push(
        `/user/workspace/${workspaceId}/pipeline/${pipelineId}/historydetail/${id}`,
        {
          info,
        },
      );
    },
    [history, pipelineId, workspaceId],
  );

  const [list, setList] = useState([]);
  useEffect(() => {
    getPipelineHistory(pipelineId, setList);
  }, [pipelineId]);

  return (
    <div className={cx('modal')}>
      <Table
        columns={columns}
        data={list}
        totalRows={list.length}
        hideSearchBox
        selectableRows={false}
        onRowClick={handleRowClick}
        onSortHandler={onSortHandler}
      />
    </div>
  );
}
