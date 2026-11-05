import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import {
  getCollectHistory,
  getCollectInfo,
} from '@src/apis/flightbase/dataset/collect';
import { STATUS_SUCCESS } from '@src/network';

import PromptTab from '../../llm/PromptContent/PromptTab';
import DataCollect from './DataCollect';
import DataCollectDetailHeader from './DataCollectDetailHeader';
import DataCollectInfo from './DataCollectInfo';

// CSS Module
import classNames from 'classnames/bind';
import style from './UserDatasetCollectDetailContent.module.scss';

const cx = classNames.bind(style);

const initial = {
  collect_info: {
    name: '-',
    describe: '-',
    dataset_id: 0,
    dataset_path: '-',
    instance_id: '-',
    collect_method: '-',
    collect_cycle: 0,
    collect_cycle_unit: '-',
    collect_storage_limit: 0,
    collect_storage_size: 0,
    collect_storage_unit: '-',
    collect_information_list: [],
    members: [],
    create_datetime: '0000-00-00 00:00:00',
    update_datetime: '0000-00-00 00:00:00',
    access: 0,
    instance_count: 0,
    dataset_name: '-',
    owner: '-',
  },
  status: null,
  instance_info: {
    instance_name: '-',
    instance_count: 0,
    instance_type: '-',
    gpu_allocate: 0,
    cpu_allocate: 0,
    ram_allocate: 0,
    npu_allocate: 0,
    gpu_name: '-',
  },
  instance_usage_info: {
    cpu: {
      available: true,
      available_cpu_core: 0,
    },
    memory: {
      available: true,
      available_memory: 0,
    },
  },
};

export default function UserDatasetCollectDetailContent() {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { id: workspaceId, did: id } = match.params;

  const tabList = useMemo(() => {
    return [
      {
        label: t('information.label'),
        value: 0,
      },
      { label: t('collect.label'), value: 1 },
    ];
  }, [t]);

  const [tabValue, setTabValue] = useState(0);
  const isExcuteBtn = tabValue === 1;

  const [info, setInfo] = useState(initial);
  const { collect_info, status } = info;
  const { name, collect_method } = collect_info;

  const getCollectInfoValue = useCallback(async () => {
    const { status, message, result } = await getCollectInfo(workspaceId, id);
    if (status === STATUS_SUCCESS) {
      setInfo(result);
    } else {
      toast.error(message);
    }
  }, [id, workspaceId]);

  const handleTab = useCallback((v) => {
    setTabValue(v);
  }, []);

  const [list, setList] = useState([]);
  const getHistoryList = useCallback(async () => {
    const { result, message, status } = await getCollectHistory(id);
    if (status === STATUS_SUCCESS) {
      setList(result);
    } else {
      toast.error(message);
    }
  }, [id]);

  useEffect(() => {
    let interval = setInterval(() => {
      getCollectInfoValue();
    }, 1000);
    getHistoryList();
    getCollectInfoValue();

    return () => clearInterval(interval);
  }, [getCollectInfoValue, getHistoryList]);

  useEffect(() => {
    if (tabValue === 0) return;

    let interval = setInterval(() => {
      getHistoryList();
    }, 1000);

    return () => clearInterval(interval);
  }, [getHistoryList, info.status, tabValue]);

  return (
    <div className={cx('data-detail-cont')}>
      <DataCollectDetailHeader
        isExcuteBtn={isExcuteBtn}
        id={id}
        name={name}
        collect_method={collect_method}
        status={status}
        getHistoryList={getHistoryList}
        getCollectInfoValue={getCollectInfoValue}
      />
      <PromptTab
        tabList={tabList}
        selectedTab={tabValue}
        handleTab={handleTab}
      />
      {tabValue === 0 && <DataCollectInfo info={info} />}
      {tabValue === 1 && (
        <DataCollect
          status={status}
          collect_method={collect_method}
          list={list}
          getHistoryList={getHistoryList}
        />
      )}
    </div>
  );
}
