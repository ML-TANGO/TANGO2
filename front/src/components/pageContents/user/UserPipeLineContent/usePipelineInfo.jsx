import { useCallback, useEffect, useState } from 'react';
import { toast } from 'react-toastify';

import { getPipelineInfoApi } from '@src/apis/flightbase/pipeline';
import { STATUS_SUCCESS } from '@src/network';

const intial = {
  pipeline_info: {
    id: 0,
    name: '-',
    create_datetime: '0000-00-00 00:00:00',
    owner_name: '-',
    create_user_name: '-',
    description: '-',
    update_datetime: '0000-00-00 00:00:00',
  },
  dataset_info: {
    id: 0,
    name: '-',
    description: '-',
    create_user_name: '-',
    create_datetime: '0000-00-00 00:00:00',
  },
  restart_setting: {
    type: null,
    unit: null,
    value: 0,
  },
};

const usePipelineInfo = (pipelineId, tab) => {
  const [info, setInfo] = useState(intial);
  const { dataset_info, pipeline_info, restart_setting } = info;

  const getPipelineInfo = useCallback(async () => {
    const { result, message, status } = await getPipelineInfoApi(
      pipelineId,
      setInfo,
    );

    if (status === STATUS_SUCCESS) {
      setInfo(result);
    } else {
      toast.error(message);
    }
  }, [pipelineId]);

  useEffect(() => {
    if (tab === 0) {
      getPipelineInfo();
    }
  }, [getPipelineInfo, pipelineId, tab]);

  return {
    getPipelineInfo,
    datasetInfo: dataset_info,
    pipeline_info,
    restart_setting,
  };
};

export default usePipelineInfo;
