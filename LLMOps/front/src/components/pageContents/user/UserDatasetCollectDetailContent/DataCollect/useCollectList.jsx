import { useCallback, useState } from 'react';

import { indexOf } from 'lodash';

import { calPlusNineHours } from '@src/utils';

export const calColumn = (collect_method) => {
  if (collect_method === 'public_api')
    return [
      {
        name: 'API 이름',
        selector: 'name',
        sortable: true,
        center: true,
        minWidth: '240px',
        grow: 240,
        cell: ({ collect_information }) => {
          return <>{collect_information.name}</>;
        },
      },
      {
        name: 'API URL',
        selector: 'url',
        sortable: true,
        minWidth: '400px',
        grow: 400,
        center: true,
        cell: ({ collect_information }) => {
          return <>{collect_information.url}</>;
        },
      },
      {
        name: 'API Key',
        selector: 'serviceKey',
        sortable: true,
        center: true,
        minWidth: '340px',
        grow: 340,
        cell: ({ collect_information }) => {
          return (
            <>
              {collect_information.jsonData.serviceKey ?? 'key 값 없음 주세요'}
            </>
          );
        },
      },
      {
        name: '제공 기관',
        selector: 'providing_organization',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ collect_information }) => {
          return <>{collect_information.providing_organization}</>;
        },
      },
      {
        name: '수집 일시',
        selector: 'create_datetime',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ create_datetime }) => {
          return <>{calPlusNineHours(create_datetime)}</>;
        },
      },
      {
        name: '수집 결과',
        selector: 'status',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ status }) => {
          return <>{status === 200 ? '성공' : '실패'}</>;
        },
      },
    ];

  if (collect_method === 'crawling')
    return [
      {
        name: '웹 크롤러 이름',
        selector: 'name',
        sortable: true,
        center: true,
        minWidth: '592px',
        grow: 592,
        cell: ({ collect_information }) => {
          return <>{collect_information.name}</>;
        },
      },
      {
        name: '웹 크롤러 URL',
        selector: 'url',
        sortable: true,
        center: true,
        minWidth: '592px',
        grow: 592,
        cell: ({ collect_information }) => {
          return <>{collect_information.url}</>;
        },
      },
      {
        name: '수집 일시',
        selector: 'create_datetime',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ create_datetime }) => {
          return <>{calPlusNineHours(create_datetime)}</>;
        },
      },
      {
        name: '수집 결과',
        selector: 'status',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ status }) => {
          return <>{status === 200 ? '성공' : '실패'}</>;
        },
      },
    ];

  if (collect_method === 'remote_server')
    return [
      {
        name: '원격 서버 이름',
        selector: 'name',
        sortable: true,
        center: true,
        minWidth: '240px',
        grow: 240,
        cell: ({ collect_information }) => {
          return <>{collect_information.name}</>;
        },
      },
      {
        name: '원격 서버 URL',
        selector: 'ip',
        sortable: true,
        center: true,
        minWidth: '352px',
        grow: 352,
        cell: ({ collect_information }) => {
          return <>{collect_information.ip ?? '-'}</>;
        },
      },
      {
        name: 'ID',
        selector: 'user',
        sortable: true,
        center: true,
        minWidth: '260px',
        grow: 260,
        cell: ({ collect_information }) => {
          return <>{collect_information.user ?? '-'}</>;
        },
      },
      {
        name: '수집 데이터 경로',
        selector: 'path',
        sortable: true,
        center: true,
        minWidth: '300px',
        grow: 300,
        cell: ({ collect_information }) => {
          return <>{collect_information.path}</>;
        },
      },
      {
        name: '수집 일시',
        selector: 'create_datetime',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ create_datetime }) => {
          return <>{calPlusNineHours(create_datetime)}</>;
        },
      },
      {
        name: '수집 결과',
        selector: 'status',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ status }) => {
          return <>{status === 200 ? '성공' : '실패'}</>;
        },
      },
    ];
  if (collect_method === 'flightbase') {
    return [
      {
        name: '배포 프로젝트',
        selector: 'name',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ collect_information }) => {
          return <>{collect_information.name}</>;
        },
      },
      {
        name: '프로젝트 생성자',
        selector: 'user_name',
        sortable: true,
        center: true,
        minWidth: '172px',
        grow: 172,
        cell: ({ collect_information }) => {
          return <>{collect_information.user_name}</>;
        },
      },
    ];
  }
  return [];
};

export const calData = (list, collect_method) => {
  if (collect_method === 'public_api') {
    const shallowCopyList = list.slice();
    const returnList = shallowCopyList.map((info) => {
      return {
        ...info,
        ...info.collect_info,
      };
    });
    return returnList.reverse();
  }

  if (collect_method === 'crawling') {
    const shallowCopyList = list.slice();
    const returnList = shallowCopyList.map((info) => {
      return {
        ...info,
      };
    });
    return returnList.reverse();
  }
  if (collect_method === 'remote_server') {
    const shallowCopyList = list.slice();
    const returnList = shallowCopyList.map((info) => {
      return {
        ...info,
      };
    });
    return returnList.reverse();
  }
  if (collect_method === 'flightbase') {
    const shallowCopyList = list.slice();
    const returnList = shallowCopyList.map((info) => {
      return {
        ...info,
      };
    });
    return returnList;
  }

  return [];
};

const calSelectOptions = (columns) => {
  const copyList = columns.slice();

  const shallowCopyList = copyList.slice();
  const columnsList = shallowCopyList.map((info) => {
    return {
      label: info.name,
      value: info.selector,
    };
  });
  return columnsList;
};

const calKeyword = (selectedValue, data, keyword) => {
  const shallowList = data.slice();
  const filterList = shallowList.filter((info) => {
    if (selectedValue.value === 'serviceKey') {
      return info.collect_information.jsonData[selectedValue.value].includes(
        keyword,
      );
    }
    if (selectedValue.value === 'create_datetime') {
      return info.create_datetime.includes(keyword);
    }

    if (selectedValue.value === 'status') {
      return `${info.status}`.includes(keyword);
    }

    return info.collect_information[selectedValue.value].includes(keyword);
  });
  return filterList;
};

const useCollectList = (list, collect_method, getHistoryList) => {
  const columns = calColumn(collect_method);
  const data = calData(list, collect_method);

  const selectOptions = calSelectOptions(columns);
  const [selectedValue, setSelectedValue] = useState(selectOptions[0]);

  const [keyword, setKeyword] = useState('');
  const handleKeyword = useCallback((e) => {
    setKeyword(e.target.value);
  }, []);
  const handleKeywordReset = useCallback(() => {
    setKeyword('');
  }, []);

  const filterData = calKeyword(selectedValue, data, keyword);

  const handleSelectOption = useCallback((info) => {
    setSelectedValue(info);
  }, []);

  const handleDelete = useCallback(async (selectedRows) => {
    console.log(selectedRows);
    // const { status, message } = await postCollectDelete();
    // if (status === STATUS_SUCCESS) {
    //   await getHistoryList();
    // } else {
    //   toast.error(message);
    // }
  }, []);

  const [selectedRows, setSelectedRows] = useState([]);
  const handleSelectedItem = useCallback(({ selectedRows }) => {
    const shallowList = selectedRows.slice();
    setSelectedRows(selectedRows);
  }, []);

  return {
    data: filterData,
    columns,
    selectOptions,
    selectedValue: selectedValue.value,
    keyword,
    handleKeyword,
    handleKeywordReset,
    handleSelectOption,
    handleDelete,
    handleSelectedItem,
  };
};

export default useCollectList;
