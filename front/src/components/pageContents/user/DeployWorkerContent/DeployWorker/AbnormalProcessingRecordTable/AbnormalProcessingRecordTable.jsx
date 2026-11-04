// Components
import { Button, Tooltip } from '@jonathan/ui-react';

// Icon
import download from '@src/static/images/icon/00-ic-data-download-blue.svg';
import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import Table from '@src/components/molecules/Table';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';

// CSS Module
import classNames from 'classnames/bind';
import style from './AbnormalProcessingRecordTable.module.scss';

const cx = classNames.bind(style);

function AbnormalProcessingRecordTable({ data, onDownload }) {
  const { t } = useTranslation();
  const [tableData, setTableData] = useState([]);
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(4);

  useEffect(() => {
    const newData = [...data];
    setTableData(newData);
  }, [data]);

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('datetime.label')}
          idx={0}
        />
      ),
      selector: 'time_local',
      sortable: true,
      minWidth: '160px',
      maxWidth: '200px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('worker.label')}
          idx={1}
        />
      ),
      selector: 'worker',
      sortable: true,
      maxWidth: '120px',
      cell: ({ worker }) => {
        return `${t('worker.label')} ${worker}`;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('statusCode.label')}
          idx={2}
        />
      ),
      selector: 'status',
      sortable: true,
      minWidth: '120px',
      maxWidth: '150px',
    },
    {
      name: t('message.label'),
      selector: 'message',
      sortable: false,
      minWidth: '200px',
      cell: ({ message }) => {
        return message || <div>-</div>;
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('endpoint.label')}
          idx={3}
        />
      ),
      selector: 'request',
      sortable: true,
      minWidth: '200px',
      cell: ({ request }) => {
        return <div title={request}>{request}</div>;
      },
    },
  ];

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  return (
    <div className={cx('abnormal-processing-record')}>
      <span>
        <div className={cx('abnormal-title-wrap')}>
          <label>
            <span>{t('abnormalProcessingRecord.label')}</span>
            <Tooltip
              contents={t('abnormalProcessingRecord.tooltip.message')}
              contentsAlign={{ horizontal: 'left' }}
              iconCustomStyle={{ width: '20px' }}
            />
          </label>
          <Button
            type='primary-reverse'
            icon={download}
            iconAlign='right'
            onClick={onDownload}
            disabled={tableData?.length === 0}
          >
            CSV {t('download.label')}
          </Button>
        </div>
      </span>
      <div className={cx('table-wrap')}>
        <Table
          columns={columns}
          data={tableData}
          totalRows={data.length}
          hideSearchBox={true}
          selectableRows={false}
          defaultSortField='time_local'
          onSortHandler={onSortHandler}
        />
      </div>
    </div>
  );
}

export default AbnormalProcessingRecordTable;
