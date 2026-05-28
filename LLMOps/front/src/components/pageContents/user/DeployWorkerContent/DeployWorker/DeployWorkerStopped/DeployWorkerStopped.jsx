// Components
import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import { Button } from '@jonathan/ui-react';

import { convertDuration } from '@src/datetimeUtils';

import DeployLogDownloadBtn from '@src/components/molecules/DeployLogDownloadBtn';
import Table from '@src/components/molecules/Table';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';

// Actions
import { openConfirm } from '@src/store/modules/confirm';

// Utils
import {
  convertBinaryByte,
  formatSecondsToDHMS,
  numberWithCommas,
} from '@src/utils';

// CSS Module
import classnames from 'classnames/bind';
import style from './DeployWorkerStopped.module.scss';

const cx = classnames.bind(style);

function DeployWorkerStopped({
  did,
  getStoppedData,
  checkedData,
  onSelect,
  toggledClear,
  workerDownHandler,
  inputValueHandler,
  keyword,
  tableData,
  selectInputHandler,
  searchKey,
  workerDeleteClickHandler,
  workerMemoModalHandler,
  title,
}) {
  const { t } = useTranslation();

  // Router Hooks
  const history = useHistory();
  const { id: wid } = useParams();

  // Redux Hooks
  const dispatch = useDispatch();
  const [logDownOptions, setLogDownOptions] = useState({
    nginx: true,
    api: true,
  });

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(6);

  /**
   * 시간 단위 나눠주는 핸들러
   * @param {string} time
   */
  const changeTimeHandler = (time) => {
    return time?.replace(/-/gi, '.');
  };

  /**
   * 로그 다운로드 - 체크 여부 boolean값 변경 핸들러 (nginx, api)
   * @param {string} option
   */
  const logDownOptionsHandler = (option) => {
    setLogDownOptions({ ...logDownOptions, [option]: !logDownOptions[option] });
  };

  /**
   * 메모 수정 클릭 시 이전 메모 내용을 보이기 위한 핸들러
   * @param {number} id
   */
  const memoModalClickHandler = (id) => {
    const prevMemo = tableData?.filter(
      (data) => data.deployment_worker_id === id,
    )[0].description;
    workerMemoModalHandler(id, prevMemo);
    // id와 이전 메모 내용을 넘김
  };

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('worker.label')}
          idx={0}
        />
      ),
      selector: 'deployment_worker_id',
      sortable: true,
      minWidth: '120px',
      maxWidth: '154px',
      cell: ({ deployment_worker_id: id }) => {
        return `${t('worker.label')} ${id}`;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('startTime.label')}
          idx={1}
        />
      ),
      selector: 'start_datetime',
      sortable: true,
      minWidth: '100px',
      maxWidth: '169px',
      cell: ({ start_datetime: time }) => {
        return time ? changeTimeHandler(time) : '-';
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('stopTime.label')}
          idx={2}
        />
      ),
      selector: 'end_datetime',
      sortable: true,
      minWidth: '100px',
      maxWidth: '169px',
      cell: ({ end_datetime: time }) => {
        return time ? changeTimeHandler(time) : '-';
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('operationTime.label')}
          idx={3}
        />
      ),
      selector: 'operation_time',
      sortable: true,
      minWidth: '150px',
      maxWidth: '160px',
      cell: ({ operation_time: time }) => {
        return time > 0 ? formatSecondsToDHMS(time) : '-';
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('callCount.label')}
          idx={4}
        />
      ),
      selector: 'call_count',
      sortable: true,
      maxWidth: '131px',
      cell: ({ call_count: count }) => {
        return count ? numberWithCommas(count) : 0;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('size.label')}
          idx={5}
        />
      ),
      selector: 'log_size',
      sortable: true,
      maxWidth: '110px',
      cell: ({ log_size: size }) => {
        return convertBinaryByte(size);
      },
    },
    {
      name: t('memo.label'),
      selector: 'description',
      minWidth: '210px',
      cell: ({ description }) => {
        return <div title={description}>{description || '-'}</div>;
      },
    },
    {
      name: t('memoChange.label'),
      maxWidth: '105px',
      cell: ({ deployment_worker_id: id }) => {
        return (
          <img
            className='table-icon'
            src='/images/icon/00-ic-basic-pen.svg'
            alt='edit'
            onClick={() => memoModalClickHandler(id)}
          />
        );
      },
      button: true,
    },
  ];

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  /**
   * 로그 다운로드 함수에게 파라미터 넘겨주는 핸들러
   */
  const logDownClickHandler = () => {
    let nginx = logDownOptions.nginx;
    let api = logDownOptions.api;
    let checkedId = [];
    checkedData.map((data) => checkedId.push(data.deployment_worker_id));
    workerDownHandler(did, checkedId.join(', '), nginx, api);
  };

  /**
   * 삭제 모달 불러오는 함수
   */
  const openDeleteWorkerModal = () => {
    dispatch(
      openConfirm({
        title: 'deleteWorkerPopup.title.label',
        content: 'deleteWorker.title.message',
        submit: {
          text: 'delete.label',
          func: () => {
            workerDeleteClickHandler(checkedData);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteWorker.message'),
        confirmMessage: t('deleteWorker.label'),
      }),
    );
  };

  const searchOptions = [
    { label: 'all.label', value: 'all' },
    { label: 'worker.label', value: 'deployment_worker_id' },
    { label: 'memo.label', value: 'description' },
  ];

  /**
   * input 초기화 함수
   */
  const onClear = () => {
    inputValueHandler('');
  };

  /**
   * table row 클릭
   */
  const onRowClick = (row) => {
    const {
      deployment_worker_id: workerId,
      permission_level: permissionLevel,
    } = row;
    history.push({
      pathname: `/user/workspace/${wid}/deployments/${did}/workers/${workerId}/worker`,
      state: {
        workerStatus: 'stop',
        title,
        permissionLevel,
      },
    });
  };

  useEffect(() => {
    getStoppedData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const bottomButtonList = (
    <>
      <Button
        type='red'
        onClick={openDeleteWorkerModal}
        disabled={
          checkedData.length === 0 || checkedData[0]?.permission_level > 3
        }
        customStyle={{
          backgroundColor: '#FFE6E5',
          border: 'none',
          color: '#FA4E57',
          fontWeight: 700,
        }}
      >
        {t('delete.label')}
      </Button>
      <DeployLogDownloadBtn
        btnRender={() => (
          <Button
            type='primary'
            disabled={checkedData.length === 0}
            customStyle={{
              backgroundColor: '#DEE9FF',
              border: 'none',
              color: '#2D76F8',
              fontWeight: 700,
            }}
          >
            {t('logDownload.label')}
          </Button>
        )}
        logDownOptions={logDownOptions}
        logDownOptionsHandler={logDownOptionsHandler}
        logDownClickHandler={logDownClickHandler}
      />
    </>
  );

  return (
    <div className={cx('worker-stopped-wrap')}>
      <div className={cx('table')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={tableData?.length}
          bottomButtonList={bottomButtonList}
          hideButtons={tableData?.length === 0}
          defaultSortField='end_datetime'
          onSelect={onSelect}
          toggledClearRows={toggledClear}
          searchKey={searchKey}
          searchOptions={searchOptions}
          keyword={keyword}
          onSearchKeyChange={(value) => {
            selectInputHandler(value);
          }}
          onSearch={(e) => {
            inputValueHandler(e.target.value);
          }}
          onClear={onClear}
          onRowClick={onRowClick}
          onSortHandler={onSortHandler}
        />
      </div>
    </div>
  );
}

export default DeployWorkerStopped;
