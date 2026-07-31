// Components

// Utils
import { Tooltip } from '@tango/ui-react';

import { convertLocalTime } from '@src/datetimeUtils';
import TrainingResultIcon from '@src/static/images/icon/00-ic-training-result-icon.svg';
import TrashIcon from '@src/static/images/icon/00-ic-trash.svg';
import WarningIcon from '@src/static/images/icon/ic-warning-yellow-white.svg';
import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory } from 'react-router-dom';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

import JobListContent from '../JobListContent';
import JobStatus from './JobStatus';

import classNames from 'classnames/bind';
// CSS module
import style from './JobList.module.scss';

const cx = classNames.bind(style);

const statusObj = {
  done: 'job.done',
  stop: 'stop',
  pending: 'job.pending',
  scheduling: 'job.pending',
  installing: 'job.installing',
  running: 'job.running',
  error: 'job.error',
};

const calReturnJobStatus = (status) => {
  if (!statusObj[status]) return 'none.label';
  return statusObj[status];
};

// const calReturnTooltipMessage = (resourceType, t) => {
//   if (resourceType === 'cpu') {
//     return t('job.cpu.fail.message');
//   }
//   return t('job.gpu.fail.message');
// };

const JobList = ({
  data,
  trainingInfo,
  openDeleteConfirmPopup,
  onSelect,
  onViewLog,
  selectedRows,
  onStopJob,
  isLoadingStopBtn,
  tid,
  wid,
  isAllOpen,
  manualOpenHandler,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();

  const { id: traingId, type: trainingType } = trainingInfo;

  const {
    name,
    group_id: groupId,
    options,
    id,
    allocate: gpuCount,
    status,
    status_counting: statusCount,
    start_datetime: startTime,
    end_datetime: endTime,
    resource_name: resourceName,
    image_name: dockerImage,
    dataset_name: dataset,
    create_datetime: createDatetime,
    log_file: logFile,
    creator,
    jobs,
    parameter,
    run_code: runCode,
  } = data;

  const [isOpen, setIsOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const isAccel = options?.gpu_acceleration === 1;
  const isUM = options?.um === 1;
  const isRDMA = options?.dma === 1;
  const [checkpointList, setCheckpointList] = useState(false);
  const [jobIdx, setJobIdx] = useState(0);

  const resourceType = resourceName ? 'gpu' : 'cpu';

  /**
   * Deploymnet 생성 모달
   */
  const onCreateDeployment = (jobName, jobIdx) => {
    dispatch(
      openModal({
        modalType: 'CREATE_DEPLOYMENT',
        modalData: {
          submit: {
            text: t('create.label'),
            func: () => {
              dispatch(closeModal('CREATE_DEPLOYMENT'));

              dispatch(
                openConfirm({
                  title: 'moveDeploymentPopup.label',
                  content: 'moveDeploymentPopup.message',
                  submit: {
                    text: 'move.label',
                    func: () => {
                      history.push({
                        pathname: `/user/workspace/${wid}/deployments`,
                      });
                    },
                  },
                  cancel: {
                    text: 'cancel.label',
                  },
                }),
              );
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
          workspaceId: wid,
          checkpoint: true,
          jobName,
          jobIdx,
          modelName: trainingInfo?.name,
          dockerImageName: dockerImage,
          fromTraining: true,
        },
      }),
    );
  };

  /**
   * 배포생성 모달 open 여부 API 호출
   * GET
   *
   */
  const detailOpenHandler = async () => {
    manualOpenHandler(null);
    setIsOpen(!isOpen);
    // getCheckpointList();
  };

  const handleLogModal = async (logFile) => {
    if (!logFile) return;
    const modalType = 'SYSTEM_LOG';

    dispatch(
      openModal({
        modalType,
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              dispatch(closeModal(modalType));
            },
          },
          traingId: id,
          projectName: name,
        },
      }),
    );
  };

  // 체크포인트 유무 주기적 확인
  // useIntervalCall(getCheckpointList, 5000);

  useEffect(() => {
    if (isAllOpen) {
      setIsOpen(true);
      // getCheckpointList();
    } else if (isAllOpen === false) {
      // null 값도 존재
      setIsOpen(false);
    }
  }, [isAllOpen]);

  return (
    <div
      id={`Job_${name}`}
      className={cx('list-box', isOpen && parameter && 'open')}
    >
      {isOpen && parameter && 'open' && (
        <div className={cx('center-border')}></div>
      )}
      <div className={cx('arrow-cont')}>
        <img
          src='/images/icon/ic-left.svg'
          alt='open'
          className={cx('arrow-btn', isOpen && 'open')}
          onClick={() => detailOpenHandler()}
        />
      </div>
      <div className={cx('group-head', isOpen && 'open')}>
        <div className={cx('first')}>
          <div className={cx('first-content-cont')}>
            <div className={cx('fixed-div')}>
              <button
                className={cx('log-btn', !logFile && 'disabled')}
                onClick={() => handleLogModal(logFile)}
              >
                {t('systemLog.label')}
              </button>
              <div className={cx('status-cont')}>
                <JobStatus
                  status={calReturnJobStatus(status.status)}
                  type='dark'
                />
              </div>
              <div className={cx('job-info-box')}>
                <div className={cx('group-name')}>{name}</div>
                <label className={cx('date-label')}>
                  {convertLocalTime(createDatetime)}
                </label>
              </div>
            </div>
            <div className={cx('docker-image-cont')}>
              <label className={cx('label')}>{t('dockerImage.label')}</label>
              <span className={cx('value')} title={dockerImage}>
                {dockerImage || '-'}
              </span>
            </div>
            {trainingType !== 'built-in' && (
              <div className={cx('run-code')}>
                <label className={cx('label')}>{t('runCode.label')}</label>
                <span className={cx('value')} title={runCode}>
                  {runCode}
                </span>
              </div>
            )}
          </div>
          <div className={cx('tool-box')}>
            <div className={cx('flex-cont')}>
              {status.status === 'error' && (
                <Tooltip
                  contents={status.reason}
                  contentsAlign={{ horizontal: 'right' }}
                  globalCustomStyle={{
                    width: '24px',
                    height: '24px',
                  }}
                  contentsCustomStyle={{
                    position: 'absolute',
                    top: '-12px',
                    right: '28px',
                    minWidth: '100%',
                    border: '1px solid #DEE9FF',
                    borderRadius: '4px',
                    boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                    padding: '16px',
                  }}
                  icon={WarningIcon}
                  iconCustomStyle={{ width: '24px', height: '24px' }}
                />
              )}
              {logFile && (
                <div
                  className={cx('train-result-btn')}
                  onClick={() => onViewLog(parameter, name, data)}
                >
                  <img src={TrainingResultIcon} alt='training-result-btn-img' />
                  <span>{t('training.result.label')}</span>
                </div>
              )}
            </div>
            <img
              src={TrashIcon}
              className={cx('delete')}
              alt='delete-icon'
              onClick={() => openDeleteConfirmPopup(id, false)}
            />
          </div>
        </div>
        {isOpen && parameter && (
          <JobListContent
            key={id}
            trainingId={id}
            trainingType={trainingType}
            resourceType={resourceType}
            jobName={name}
            logFile={logFile}
            data={parameter}
            status={status}
            onViewLog={onViewLog}
            startTime={startTime}
            endTime={endTime}
            toolData={data}
            onSelect={onSelect}
            checked={false}
            onStopJob={onStopJob}
            isLoadingStopBtn={isLoadingStopBtn}
            onCreateDeployment={onCreateDeployment}
          />
        )}
      </div>
    </div>
  );
};

export default JobList;
