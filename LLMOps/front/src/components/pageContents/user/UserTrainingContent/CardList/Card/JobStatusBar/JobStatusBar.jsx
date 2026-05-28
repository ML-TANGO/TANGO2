import { useParams, useHistory } from 'react-router-dom';

// Components
import { Progress } from 'react-sweet-progress';
import 'react-sweet-progress/lib/style.css';

// CSS Module
import classNames from 'classnames/bind';
import style from './JobStatusBar.module.scss';
const cx = classNames.bind(style);

function JobStatusBar({ trainingId, trainingName, latestItemStatus }) {
  // Router Hooks
  const history = useHistory();
  const { id: workspaceId } = useParams();
  const { status: progressStatus, progress, type } = latestItemStatus;
  const { total, pending, status } = progressStatus; // total, running, pending, done, status

  /**
   * Job/HPS 목록으로 이동
   */
  const moveJobList = () => {
    history.push({
      pathname: `/user/workspace/${workspaceId}/trainings/${trainingId}/workbench/${type}`,
      state: {
        id: trainingId,
        name: trainingName,
        loc: ['Home', trainingName, 'Workbench', type.toUpperCase()],
      },
    });
  };

  return (
    <div
      className={`${cx('job-status-bar')} event-block`}
      onClick={moveJobList}
    >
      <div className={cx('job-progress')}>
        <div className={cx('progress-inner-box')}>
          <span className={cx('progress-label', status)} title={status}>
            {type.toUpperCase()}
          </span>
          <span className={cx('progress-status', status)}>
            ({total - pending}/{total})
          </span>
        </div>
        <Progress
          percent={progress}
          status={status !== 'stop' ? status : 'default'}
          theme={{
            running: {
              symbol: '',
              color: '#2d76f8',
              trailColor: '#dee9ff',
            },
            default: {
              symbol: '',
              color: '#c1c1c1',
              trailColor: '#dbdbdb',
            },
            pending: {
              symbol: '',
              color: '#ffc500',
              trailColor: '#fff8d9',
            },
          }}
        />
      </div>
    </div>
  );
}

export default JobStatusBar;
