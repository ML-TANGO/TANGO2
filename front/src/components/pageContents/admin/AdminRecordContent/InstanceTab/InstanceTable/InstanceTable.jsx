import { Selectbox } from '@jonathan/ui-react';

import { convertDuration, convertLocalTime } from '@src/datetimeUtils';
import { debounce } from 'lodash';
import { useCallback, useEffect, useMemo, useReducer, useState } from 'react';
import { useTranslation } from 'react-i18next';

import Table from '@src/components/molecules/Table';

import { executeWithLogging } from '@src/utils';
import { getInstanceTableInfo } from '../util';

const calGetColumns = (t) => {
  return [
    {
      name: t('workspace.label'),
      selector: 'workspace_name',
      sortable: false,
    },
    {
      name: '유형',
      selector: 'type',
      sortable: false,
      cell: ({ type }) => {
        return type;
      },
    },
    {
      name: '프로젝트 이름',
      selector: 'type_detail',
      sortable: false,
      cell: ({ type_detail }) => {
        return type_detail;
      },
    },
    {
      name: t('startTime.label'),
      selector: 'start_datetime',
      sortable: false,
      maxWidth: '200px',
      cell: ({ start_datetime: time }) => convertLocalTime(time),
    },
    {
      name: t('stopTime.label'),
      selector: 'stop_time',
      sortable: false,
      maxWidth: '200px',
      cell: ({ end_datetime: time }) =>
        time !== '-' ? convertLocalTime(time) : time,
    },
    {
      name: t('uptime.label'),
      selector: 'period',
      sortable: false,
      maxWidth: '200px',
      cell: ({ period }) => {
        return convertDuration(period);
      },
    },
  ];
};

const calGetTypeOption = (t) => {
  return [
    { label: t('allUsageType.label'), value: 'all' },
    { label: t('editor.label'), value: 'editor' },
    { label: t('job.label'), value: 'job' },
    { label: t('hps.label'), value: 'hyperparamsearch' },
    { label: t('deployment.label'), value: 'deployment' },
  ];
};

const TABLE_ACTION_TYPE = {
  TYPE: 'TYPE',
  KEYWORD: 'KEYWORD',
  PAGE: 'PAGE',
  SIZE: 'SIZE',
};

const tableReducer = (state, action) => {
  switch (action.type) {
    case TABLE_ACTION_TYPE.TYPE:
      return {
        ...state,
        type: action.value,
      };
    case TABLE_ACTION_TYPE.KEYWORD:
      return {
        ...state,
        search_term: action.value,
      };
    case TABLE_ACTION_TYPE.PAGE:
      return {
        ...state,
        page: action.value,
      };
    case TABLE_ACTION_TYPE.SIZE:
      return {
        ...state,
        size: action.value,
      };
    default:
      return state;
  }
};

const InstanceTable = ({ workspace, workspaceOptions, dateState }) => {
  const { t } = useTranslation();
  const columns = useMemo(() => {
    return calGetColumns(t);
  }, [t]);
  const typeOptions = useMemo(() => {
    return calGetTypeOption(t);
  }, [t]);

  // ** [REQ TABLE DATA] **
  const initialTableState = useMemo(() => {
    return {
      page: 1,
      size: 10,
      type: { label: t('allUsageType.label'), value: 'all' },
      search_key: null,
      search_term: '',
    };
  }, [t]);
  const [tableState, tableDispatch] = useReducer(
    tableReducer,
    initialTableState,
  );
  const { page, size, type, search_term } = tableState;

  // ** [RES TABLE DATA]**
  const [resTable, setResTable] = useState({
    total: 0,
    count: size,
    histories: [],
    last_idx: {
      not: '',
    },
  });
  const { total, histories } = resTable;

  console.log('histories', histories);

  // ** [TABLE HANDLER] **
  const handleTable = useCallback((v, tableDispatch, type) => {
    tableDispatch({
      type,
      value: v,
    });
  }, []);

  // ** [TYPE SELECT BOX COMPONENT] **
  const componentTypeSelectBox = useMemo(() => {
    return (
      <Selectbox
        t={t}
        size='medium'
        list={typeOptions}
        selectedItem={type}
        customStyle={{
          selectboxForm: {
            width: '184px',
          },
          listForm: {
            width: '184px',
          },
        }}
        onChange={(v) => {
          handleTable(v, tableDispatch, TABLE_ACTION_TYPE.TYPE);
        }}
      />
    );
  }, [typeOptions, type, t, handleTable]);

  // ** [DATA FETCHING] **
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const debounceFunc = debounce(async () => {
      await executeWithLogging(async () => {
        const result = await getInstanceTableInfo(
          workspace,
          dateState,
          type.value,
          page,
          size,
          search_term,
          signal,
        );
        setResTable(result);
      });
    }, 250);

    debounceFunc();

    return () => {
      controller.abort();
      debounceFunc.cancel();
    };
  }, [dateState, page, size, workspace, search_term, type]);

  return (
    <div>
      <Table
        columns={columns}
        data={histories}
        totalRows={total}
        selectableRows={false}
        onChangeRowsPerPage={(v) =>
          handleTable(v, tableDispatch, TABLE_ACTION_TYPE.SIZE)
        }
        onChangePage={(v) =>
          handleTable(v, tableDispatch, TABLE_ACTION_TYPE.PAGE)
        }
        defaultSortField='time_stamp'
        toggledClearRows={false}
        hideButtons
        filterList={componentTypeSelectBox}
        searchOptions={[{ label: t('workspace.label'), value: 'workspace' }]}
        searchKey={{ label: t('workspace.label'), value: 'workspace' }}
        keyword={search_term}
        onSearch={(e) => {
          handleTable(e.target.value, tableDispatch, TABLE_ACTION_TYPE.KEYWORD);
        }}
        onClear={() => {
          handleTable('', tableDispatch, TABLE_ACTION_TYPE.KEYWORD);
        }}
        paginationServer
      />
    </div>
  );
};

export default InstanceTable;
