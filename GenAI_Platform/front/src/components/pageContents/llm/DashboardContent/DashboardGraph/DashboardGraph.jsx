import { getDashbaordUserResourceUsage } from '@src/apis/llm/dashboard';
import React, { useEffect, useState } from 'react';
import { toast } from 'react-toastify';

import WorkSpaceResourceChart from '@src/components/pageContents/user/UserHomeContent/WorkSpaceResourceChart';

import { STATUS_SUCCESS } from '@src/network';

import DashboardFrame from '../DashboardFrame';

const initial = {
  cpu: [],
  gpu: [],
  network: [],
  ram: [],
  storage_data: [],
  storage_main: [],
};

const getGraphData = async (workspaceId, setGraphData) => {
  const { status, result, message } = await getDashbaordUserResourceUsage(
    workspaceId,
  );
  if (status === STATUS_SUCCESS) {
    setGraphData(result.timeline ?? initial);
  } else {
    toast.error(message);
  }
};

const DashboardGraph = React.memo(({ title, workspaceId }) => {
  const [graphData, setGraphData] = useState(initial);

  useEffect(() => {
    getGraphData(workspaceId, setGraphData);
  }, [workspaceId]);

  return (
    <DashboardFrame title={title} style={{ height: '538px' }}>
      <WorkSpaceResourceChart
        tagId={'WorkSpaceResourceChart'}
        totalUsage={graphData}
        maxValue={100}
        customStyle={{ width: '100%', height: '360px' }}
      />
    </DashboardFrame>
  );
});

export default DashboardGraph;
