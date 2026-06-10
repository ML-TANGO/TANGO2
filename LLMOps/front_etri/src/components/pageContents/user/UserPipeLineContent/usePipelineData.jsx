import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { getPipelineDetail, putDataset } from '@src/apis/flightbase/pipeline';
import {
  handleReset,
  handleSetPipelineState,
} from '@src/store/modules/pipelineList';
import { STATUS_SUCCESS } from '@src/network';

import { calRecordTime, convertByte } from '@src/utils';

import IconBlueData from '@src/static/images/icon/00-data-blue.svg';
import IconRefresh from '@src/static/images/icon/00-ic-basic-renew-blue.svg';
import IconUseTime from '@src/static/images/icon/icon-records-blue.svg';

const initialProjectInfo = {
  tasks: {
    preprocessing_task: [],
    project_task: [],
    deployment_task: [],
  },
  pipeline_name: '-',
  create_datetime: '0000-00-00 00:00:00',
  owner_name: '-',
  create_user_name: '-',
  description: '-',
  retraining_config: {
    type: 'data',
    unit: 'TB',
    value: 0,
  },
  dataset_info: {
    id: null,
    name: '-',
    create_datetime: '0000-00-00 00:00:00',
    update_datetime: '0000-00-00 00:00:00',
    create_user_name: '-',
    description: '-',
    access: 1,
  },
  increase_size: 0,
  retraining_count: 0,
  retraining_type: 'data',
  retraining_unit: 'TB',
  retraining_value: 0,
  start_datetime: null,
  end_datetime: null,
  status: 'done',
};

const calIsStopBtn = (status, end_datetime) => {
  if (status === 'done') return false;
  if (end_datetime) return false;
  return true;
};

const calHeaderList = (retraining_count, recordTime, increase_size) => {
  const increaseValue = convertByte(increase_size);

  return [
    {
      icon: IconRefresh,
      label: '재학습 횟수',
      value: `${retraining_count} 회`,
    },
    {
      icon: IconBlueData,
      label: '데이터 증가량',
      value: `${increaseValue}`,
    },
    {
      icon: IconUseTime,
      label: '경과 시간',
      value: `${recordTime}`,
    },
  ];
};

const usePipelineData = (pipelineId, tab) => {
  const dispatch = useDispatch();

  const [projectInfo, setProjectInfo] = useState(initialProjectInfo);
  const {
    start_datetime,
    retraining_count,
    end_datetime,
    increase_size,
    status,
  } = projectInfo;

  const isLoading = useRef(false);
  const isStopBtn = calIsStopBtn(status, end_datetime);

  const recordTime = calRecordTime(start_datetime, end_datetime);
  const headerInfoList = calHeaderList(
    retraining_count,
    recordTime,
    increase_size,
  );

  const getPipelineData = useCallback(async () => {
    if (isLoading.current) return;
    isLoading.current = true;
    const { result, status, message } = await getPipelineDetail(pipelineId);
    if (status === STATUS_SUCCESS) {
      dispatch(
        handleSetPipelineState({
          type: 'all',
          data: result.tasks,
        }),
      );
      setProjectInfo(result);
    } else {
      toast.error(message);
    }
    isLoading.current = false;
  }, [dispatch, pipelineId]);

  const handleDataset = useCallback(
    async (value, pipelineId) => {
      const { status, message } = await putDataset(pipelineId, value.id);
      if (status !== STATUS_SUCCESS) {
        toast.error(message);
      } else {
        await getPipelineData();
      }
    },
    [getPipelineData],
  );

  useEffect(() => {
    if (tab !== 1) return;

    getPipelineData();

    let intervalGetInfo;
    if (isStopBtn && tab === 1) {
      intervalGetInfo = setInterval(() => {
        getPipelineData();
      }, 1000);
    } else {
      clearInterval(intervalGetInfo);
    }

    return () => {
      dispatch(handleReset());
      clearInterval(intervalGetInfo);
    };
  }, [dispatch, getPipelineData, isStopBtn, tab]);

  return {
    projectInfo,
    isStopBtn,
    headerInfoList,
    getPipelineData,
    handleDataset,
  };
};

export default usePipelineData;
