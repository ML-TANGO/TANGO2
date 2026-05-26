import { useState, useEffect, useCallback, Fragment } from 'react';
import { withRouter } from 'react-router-dom';
import PropTypes from 'prop-types';

// Components
import { Tooltip } from '@jonathan/ui-react';
import EmptyBox from '@src/components/molecules/EmptyBox';
import HpsItem from './HpsItem';
import JobItem from './JobItem';
import JupyterItem from './JupyterItem';
import OtherWsItem from './OtherWsItem';
import TrainingGroupItem from './TrainingGroupItem';
import SingleStackBarChart from '@src/components/molecules/chart/SingleStackBarChart';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

// CSS Module
import style from './QueueManager.module.scss';
import classNames from 'classnames/bind';

const cx = classNames.bind(style);
let apiCallCount = 0;
let isMount = false;

function convertChartData(data, t) {
  const { workspace, node } = data;

  const availableGpu = {
    label: t ? t('availableGpu.label') : 'Available GPU',
    // value: 0,
    value: Math.min(workspace.free, node.free),
    color: '#00c775',
  };
  const wsUseGpu = {
    label: t ? t('activeGpu.label') : 'Active GPU',
    // value: 5,
    value: workspace.used,
    color: '#e3fcee',
  };
  const unAvailableGpu = {
    label: t ? t('unavailableGpu.label') : 'Unavailable',
    // value: 1,
    value: workspace.total - workspace.free - workspace.used,
    color: '#f0f0f0',
  };

  return [wsUseGpu, availableGpu, unAvailableGpu];
}

/**
 *
 * @param {object} history react-router-dom withRouter의 history 객체
 * @param {boolean} isOpen SlidePanel 컴포넌트가 보일 때 true 안보일 때 false
 * @param {function} t 다국어 지원 함수
 * @component
 * @example
 * const isOpen = false;
 * return (
 *  <QueueManager
 *    isOpen={isOpen}
 *    t={t} // 다국어 지원 함수
 *  />
 * );
 *
 * -
 */
const QueueManager = ({ history, isOpen, t }) => {
  const {
    location: { pathname },
  } = history;

  const GPU_STATUS_HELP = (
    <>
      사용 불가능한 GPU 의 이유
      <br />
      <br />
      1. (공통) 서버 장애, 점검 등의 이유로 물리적으로 사용 가능한 GPU 개수가
      부족한 상황
      <br />
      <br />
      2. (비보장) 공유하는 GPU 자원을 이미 다른 Workspace가 사용 중이라 기다려야
      하는 상황
      <br />
      <br />
      3. (보장) 회수 되어야 할 GPU 자원이 아직 회수 되지 못한 상황 (회수를 위해
      관리자 문의 필요)
    </>
  );

  const JOB_HELP = `생성 시간 순서에 따른 정렬로 작업을 Queue 형태로 나타내며
  먼저 생성된 작업이 반드시 먼저 실행되지는 않음
  (동일한 학습에서 생성된 작업이거나 잔여 Workspace GPU 개수 상태와 같은 이유가 우선순위에 영향을 줌)`;

  const wId = pathname.split('/')[3];
  const [queueList, setQueueList] = useState([]);
  const [activeList, setActiveList] = useState([]);
  const [gpuResource, setGpuResource] = useState({
    node: { free: 0, total: 0, used: 0 },
    workspace: { free: 0, total: 0, used: 0 },
  });

  const getQueueList = useCallback(
    async (count) => {
      const response = await callApi({
        url: `pod/list_queue?workspace_id=${wId}`,
        method: 'get',
      });
      const { status, result } = response;
      if (status === STATUS_SUCCESS && isMount) {
        const {
          queue_list: qList,
          running_list: rList,
          gpu_resource: gpuResc,
        } = result;
        setQueueList(qList);
        setActiveList(rList);
        setGpuResource(gpuResc);
        setTimeout(() => {
          if (apiCallCount === count) getQueueList(apiCallCount);
        }, 1000);
      }
    },
    [wId],
  );

  const moveToTarget = useCallback(
    (wsId, tId, tName, type) => {
      history.push({
        pathname: `/user/workspace/${wsId}/trainings/${tId}/workbench/${type}`,
        state: {
          id: tId,
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
      getQueueList(apiCallCount);
    } else {
      apiCallCount += 1;
    }
    return () => {
      apiCallCount += 1;
    };
  }, [isOpen, getQueueList]);

  useEffect(() => {
    isMount = true;
    return () => {
      isMount = false;
    };
  }, []);

  const chartData = convertChartData(gpuResource, t);
  return (
    <div className={cx('queue-manager')}>
      <h3 className={cx('sticky')}>
        {t
          ? t('trainingGpuScheduler.title.label')
          : 'Training GPU Usage Scheduler'}
      </h3>
      <div className={cx('resource-status')}>
        <div className={cx('box-title')}>
          {t ? t('gpuResource.label') : 'GPU Resource'}
          <Tooltip
            contents={GPU_STATUS_HELP}
            contentsAlign={{ vertical: 'bottom', horizontal: 'center' }}
          />
        </div>
        {gpuResource.workspace.total === 0 ? (
          <EmptyBox
            customStyle={{ height: '60px', marginBottom: '20px' }}
            text={'noGPUResource.message'}
            isBox
          />
        ) : (
          <SingleStackBarChart data={chartData} />
        )}
      </div>
      <div className={cx('active-box')}>
        <p className={cx('box-title')}>
          {t ? t('activeTasks.label') : 'Active Tasks'}
          <span className={cx('info')}>
            {activeList.length > 0
              ? `${activeList.length} active job found`
              : ''}
          </span>
        </p>
        {activeList.length === 0 ? (
          <EmptyBox
            customStyle={{ height: '60px', marginBottom: '20px' }}
            text={'noData.message'}
            isBox
          />
        ) : (
          <div className={cx('list')}>
            {activeList.map((item, i) => (
              <Fragment key={i}>
                {item.item_type === 'hps' && (
                  <HpsItem {...item} moveToTarget={moveToTarget} t={t} />
                )}
                {item.item_type === 'job' && (
                  <JobItem {...item} moveToTarget={moveToTarget} t={t} />
                )}
                {item.item_type === 'tool' && <JupyterItem {...item} t={t} />}
              </Fragment>
            ))}
          </div>
        )}
      </div>
      <div className={cx('pending-box')}>
        <div className={cx('box-title')}>
          {t ? t('upcomingTasks.label') : 'Upcoming Tasks'}
          <Tooltip contents={JOB_HELP} customStyle={{ width: '180px' }} />
        </div>
        {queueList.length === 0 ? (
          <EmptyBox
            customStyle={{ height: '60px', marginBottom: '20px' }}
            text={'noData.message'}
            isBox
          />
        ) : (
          <ul className={cx('list')}>
            {queueList.map((item, i) => (
              <Fragment key={i}>
                {item.item_type === 'hps' && (
                  <HpsItem {...item} moveToTarget={moveToTarget} t={t} />
                )}
                {item.item_type === 'job' && (
                  <JobItem {...item} moveToTarget={moveToTarget} t={t} />
                )}
                {item.item_type === 'other_workspace' && (
                  <OtherWsItem {...item} t={t} />
                )}
                {item.item_type === 'training_group' && (
                  <TrainingGroupItem {...item} t={t} />
                )}
              </Fragment>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

QueueManager.propTypes = {
  history: PropTypes.object.isRequired,
  isOpen: PropTypes.bool.isRequired,
  t: PropTypes.func,
};

export default withRouter(QueueManager);
