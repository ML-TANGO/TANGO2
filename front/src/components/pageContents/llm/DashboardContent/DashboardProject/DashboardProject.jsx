import React, { useEffect, useRef, useState } from 'react';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import _ from 'lodash';

import { getProjectItems } from '@src/apis/llm/dashboard';
import { STATUS_SUCCESS } from '@src/network';

import DashboardFrame from '../DashboardFrame';
import ProjectCardList from './ProjectCardList';

const getProjectItem = async (
  workspaceId,
  isFetching,
  projectList,
  setProjectList,
) => {
  if (isFetching.current) return;
  isFetching.current = true;
  const { result, status, message } = await getProjectItems(
    workspaceId,
    'a-llm',
  );
  if (status === STATUS_SUCCESS) {
    const isEqual = JSON.stringify(result) === JSON.stringify(projectList);
    if (!isEqual) {
      setProjectList(result);
    }
  } else {
    toast.error(message);
  }
  isFetching.current = false;
};

export default function DashboardProject({ title }) {
  const match = useRouteMatch();
  const { params } = match;
  const workspaceId = params.id;

  const [projectList, setProjectList] = useState([]);
  const isFetching = useRef(false);

  useEffect(() => {
    let interval;

    getProjectItem(workspaceId, isFetching, projectList, setProjectList);
    interval = setInterval(() => {
      getProjectItem(workspaceId, isFetching, projectList, setProjectList);
    }, 2000);

    return () => {
      clearInterval(interval);
    };
  }, [projectList, workspaceId]);

  return (
    <DashboardFrame
      title={title}
      style={{ height: '560px' }}
      contentStyle={{ padding: '16px 0' }}
    >
      <ProjectCardList project_items={projectList} />
    </DashboardFrame>
  );
}
