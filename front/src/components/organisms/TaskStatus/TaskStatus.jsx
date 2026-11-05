import { useState, useEffect, useCallback, Fragment } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import Tab from '@src/components/molecules/Tab';
import JupyterItem from '../QueueManager/JupyterItem';
import JobItem from '../QueueManager/JobItem';
import HpsItem from '../QueueManager/HpsItem';
import DeployItem from '../QueueManager/DeployItem';
import EmptyBox from '@src/components/molecules/EmptyBox';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// CSS module
import classNames from 'classnames/bind';
import style from './TaskStatus.module.scss';

const cx = classNames.bind(style);

const user = sessionStorage.getItem('user_name');

let apiCallCount = 0;
function TaskStatus({ isOpen, t }) {
  const history = useHistory();
  const match = useRouteMatch();
  const wId = match.params.id;

  const taskStatusText = t ? t('taskStatus.label') : 'Task Status';
  const myTasksText = t ? t('myTasks.label') : 'My Tasks';
  const allUserTasksText = t ? t('allUserTasks.label') : 'All User Tasks';
  const currentWorkspaceText = t
    ? t('currentWorkspace.label')
    : 'Current Workspace';
  const allWorkspacesText = t ? t('allWorkspace.label') : 'All Workspaces';

  const [tab, setTab] = useState({ label: 'GPU', value: 0 });
  const option = [
    { label: 'GPU', value: 0 },
    { label: 'CPU', value: 1 },
  ];
  const [isMine, setIsMine] = useState(false);
  const [isCurrentWs, setIsCurrentWs] = useState(false);
  const [taskList, setTaskList] = useState([]);

  const getActiveTask = useCallback(
    async (count) => {
      const url = `pod/list_active${isCurrentWs ? `?workspace_id=${wId}` : ''}`;
      const response = await callApi({
        url,
        method: 'get',
      });
      const { status, result } = response;
      if (status === STATUS_SUCCESS) {
        const activeList = result.active_list;
        const jupyterGpu = activeList['jupyter-gpu'].map((d) => ({
          ...d,
          resourceType: 'gpu',
        }));
        const jobGpu = activeList['job-gpu'].map((d) => ({
          ...d,
          resourceType: 'gpu',
        }));
        const hpsGpu = activeList['hps-gpu'].map((d) => ({
          ...d,
          resourceType: 'gpu',
        }));
        const deployGpu = activeList['deployment-gpu'].map((d) => ({
          ...d,
          resourceType: 'gpu',
        }));

        const { editor } = activeList;
        const jobCpu = activeList['job-cpu'].map((d) => ({
          ...d,
          resourceType: 'cpu',
        }));
        const hpsCpu = activeList['hps-cpu'].map((d) => ({
          ...d,
          resourceType: 'cpu',
        }));
        const deployCpu = activeList['deployment-cpu'].map((d) => ({
          ...d,
          resourceType: 'cpu',
        }));
        const jupyterCpu = editor.map((d) => ({
          ...d,
          resourceType: 'cpu',
        }));

        setTaskList([
          ...jobGpu,
          ...hpsGpu,
          ...jupyterGpu,
          ...deployGpu,
          ...jobCpu,
          ...hpsCpu,
          ...jupyterCpu,
          ...deployCpu,
        ]);

        setTimeout(() => {
          if (apiCallCount === count) getActiveTask(apiCallCount);
        }, 1000);
      }
    },
    [isCurrentWs, wId],
  );

  const tabHandler = (tValue) => {
    setTab(tValue);
  };

  const userFilterHandler = () => {
    setIsMine(!isMine);
  };

  const workspaceFilterHandler = () => {
    setIsCurrentWs(!isCurrentWs);
  };

  const moveToTarget = useCallback(
    (workspaceId, trainingId, tName, type) => {
      history.push({
        pathname: `/user/workspace/${workspaceId}/trainings/${trainingId}/workbench/${type}`,
        state: {
          id: trainingId,
          name: tName,
          loc: ['Home', tName, 'Workbench', type.toUpperCase()],
          tab: type,
        },
      });
    },
    [history],
  );

  useEffect(() => {
    if (isOpen) {
      apiCallCount += 1;
      getActiveTask(apiCallCount);
    } else {
      apiCallCount += 1;
    }

    return () => {
      apiCallCount += 1;
    };
  }, [isOpen, getActiveTask, isCurrentWs]);

  const filteredList = taskList
    .filter(({ resourceType }) => {
      if (tab.value === 0 && resourceType === 'gpu') return true;
      if (tab.value === 1 && resourceType === 'cpu') return true;
      return false;
    })
    .filter(({ executor }) => {
      if (isMine && user === executor) return true;
      if (!isMine) return true;
      return false;
    });
  return (
    <div className={cx('task-status')}>
      <h3 className={cx('title')}>{taskStatusText}</h3>
      <div className={cx('filter')}>
        <Tab type='b' option={option} select={tab} tabHandler={tabHandler} />
        <button
          className={cx('switch-btn', isMine && 'active')}
          onClick={userFilterHandler}
        >
          {isMine ? myTasksText : allUserTasksText}
        </button>
        <button
          className={cx('switch-btn', isCurrentWs && 'active')}
          onClick={workspaceFilterHandler}
        >
          {isCurrentWs ? currentWorkspaceText : allWorkspacesText}
        </button>
      </div>
      {filteredList.length === 0 ? (
        <EmptyBox
          customStyle={{ height: '60px', marginBottom: '20px' }}
          text={'noData.message'}
          isBox
        />
      ) : (
        <ul className={cx('list')}>
          {filteredList.map((item, i) => (
            <Fragment key={i}>
              {item.item_type === 'job' && (
                <JobItem
                  key={i}
                  {...item}
                  hideRemainingJob
                  moveToTarget={moveToTarget}
                  t={t}
                />
              )}
              {item.item_type === 'hps' && (
                <HpsItem key={i} {...item} moveToTarget={moveToTarget} t={t} />
              )}
              {item.item_type === 'tool' && (
                <JupyterItem
                  key={i}
                  {...item}
                  moveToTarget={moveToTarget}
                  t={t}
                />
              )}
              {item.item_type === 'deployment' && (
                <DeployItem
                  key={i}
                  {...item}
                  moveToTarget={moveToTarget}
                  t={t}
                />
              )}
            </Fragment>
          ))}
        </ul>
      )}
    </div>
  );
}

export default TaskStatus;
