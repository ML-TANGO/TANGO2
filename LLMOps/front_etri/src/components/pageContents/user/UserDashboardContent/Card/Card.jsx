// i18n
import { Tooltip } from '@tango/ui-react';

// Utils
import { convertLocalTime } from '@src/datetimeUtils';
import EditIcon from '@src/static/images/icon/00-new-edit.svg';
import TrashIcon from '@src/static/images/icon/00-new-trash.svg';
import BookmarkIcon from '@src/static/images/icon/ic-star-o.svg';
import BookmarkActiveIcon from '@src/static/images/icon/ic-star.svg';
import DatasetIcon from '@src/static/images/icon/icon-datasets-black.svg';
import ActiveDatasetIcon from '@src/static/images/icon/icon-datasets-green.svg';
import DeploymentIcon from '@src/static/images/icon/icon-deployments-black.svg';
import ActiveDeploymentIcon from '@src/static/images/icon/icon-deployments-green.svg';
import DockerImageIcon from '@src/static/images/icon/icon-docker_images-black.svg';
import ActiveDockerImageIcon from '@src/static/images/icon/icon-docker_images-green.svg';
import TrainingIcon from '@src/static/images/icon/icon-trainings-black.svg';
import ActiveTrainingIcon from '@src/static/images/icon/icon-trainings-green.svg';
// Icons
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';

import { openConfirm } from '@src/store/modules/confirm';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

import CircleProgressbar, {
  calPercent,
} from '../CircleProgressbar/CircleProgressbar';

import classNames from 'classnames/bind';
// CSS module
import style from './Card.module.scss';

const cx = classNames.bind(style);

const ADMIN_EMAIL = import.meta.env.VITE_REACT_APP_ADMIN_EMAIL;

function Card({
  data,
  moveWorkspace,
  onRefresh,
  edit = false,
  onClickWorkspaceEditBtn,
  getDashboardData,
}) {
  const { t } = useTranslation();
  const {
    id,
    status,
    name,
    description,
    manager,
    user,
    trainings,
    deployments,
    images,
    datasets,
    start_datetime: startDate,
    end_datetime: endDate,
    favorites,
    resource,
  } = data;
  const dispatch = useDispatch();
  const auth = useSelector((state) => state.auth);
  const { userName } = auth;

  // 워크스페이스 별표 활성화(즐겨찿기)
  const setBookmark = async (id, action) => {
    const response = await callApi({
      url: 'workspaces/favorites',
      method: 'post',
      body: {
        workspace_id: id,
        action,
      },
    });
    const { status, error, message } = response;
    if (status === STATUS_SUCCESS) {
      onRefresh();
    } else {
      errorToastMessage(error, message);
    }
  };

  const handleDeleteWorkspace = async (id, getDashboardData) => {
    const response = await callApi({
      url: `workspaces/${id}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getDashboardData();
    } else {
      errorToastMessage(error, message);
    }
  };

  const handleDeleteWorkspacePopup = (dispatch, id, getDashboardData) => {
    dispatch(
      openConfirm({
        title: 'deleteWorkspacePopup.title.label',
        content: 'deleteWorkspacePopup.message',
        submit: {
          text: 'delete.label',
          func: async () => {
            await handleDeleteWorkspace(id, getDashboardData);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteDeploymentPopup.content.message'),
        contentCustomStyle: {
          color: 'rgba(116, 116, 116, 1)',
        },
      }),
    );
  };

  const cpuTotal = resource?.cpu?.total ?? 0;
  const cpuUsed = resource?.cpu?.used ?? 0;
  const gpuTotal = resource?.gpu?.total ?? 0;
  const gpuUsed = resource?.gpu?.used ?? 0;

  const { percentage: cpuPercent } = calPercent(cpuTotal, cpuUsed);
  const { percentage: gpuPercent } = calPercent(gpuTotal, gpuUsed);

  return (
    <div
      className={cx('card')}
      onClick={(e) => {
        if (status === 'expired' || e.target.closest('.event-block')) {
          return;
        }
        moveWorkspace(data);
      }}
    >
      <div className={cx('contents-box')}>
        <div className={cx('header')}>
          <span
            className={`${cx('bookmark-btn')} event-block`}
            onClick={() => setBookmark(id, favorites === 1 ? 0 : 1)}
          >
            <img
              className={cx('ic-star', favorites === 1 && 'active')}
              src={favorites === 1 ? BookmarkActiveIcon : BookmarkIcon}
              alt='bookmark'
            />
          </span>
          {edit && userName === manager && (
            <>
              <span
                className={`${cx('edit-btn')} event-block`}
                onClick={() => onClickWorkspaceEditBtn()}
              >
                <img className={cx('ic-edit')} src={EditIcon} alt='edit' />
              </span>
              <span
                className={`${cx('trash-btn')} event-block`}
                onClick={() =>
                  handleDeleteWorkspacePopup(dispatch, id, getDashboardData)
                }
              >
                <img
                  className={cx('ic-trash')}
                  src={TrashIcon}
                  alt='trash-btn'
                />
              </span>
            </>
          )}
          <div className={cx('card-cont')}>
            <div className={cx('status', status)}>{t(status)}</div>
            <div className={cx('status', 'manager')}>{manager}</div>
          </div>
          <div className={cx('name-box')}>
            <div className={cx('workspace-name')}>{name}</div>
            <Tooltip
              contentsCustomStyle={{
                border: '0.5px solid #DEE9FF',
                borderRadius: '10px',
                boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                padding: '0px',
              }}
              contents={
                <div className={cx('tooltip-contents')}>
                  <div className={cx('workspace-header')}>{name}</div>
                  {description && (
                    <div className={cx('description')}>{description}</div>
                  )}
                  <ul>
                    <li>
                      <label className={cx('label')}>
                        {t('workspaceManager.label')}
                      </label>
                      <span className={cx('value')}>{manager}</span>
                    </li>
                    <li>
                      <label className={cx('label')}>
                        {t('user.label')}({user?.total ?? 0})
                      </label>
                      <span className={cx('value')}>
                        {(user?.list ?? [])
                          .map(({ name }) => {
                            return name;
                          })
                          .join(', ')}
                      </span>
                    </li>
                  </ul>
                </div>
              }
              contentsAlign={{
                horizontal:
                  name.length > 15
                    ? 'right'
                    : name.length > 5
                    ? 'center'
                    : 'left',
              }}
            />
          </div>
          <div className={cx('datetime')}>
            {convertLocalTime(startDate, 'YYYY-MM-DD HH:mm')} ~{' '}
            {convertLocalTime(endDate, 'YYYY-MM-DD HH:mm')}
          </div>
        </div>
        <div className={cx('body')}>
          <div className={cx('usage-chart')}>
            <div className={cx('graph')}>
              <CircleProgressbar
                total={cpuTotal}
                used={cpuUsed}
                toolTipStyle={{ left: '-16px', top: '24px' }}
              />
            </div>
            <div className={cx('usage-text-box')}>
              <label className={cx('label')}>{t('totalCpuCount.label')}</label>
              <p className={cx('usage')}>{cpuPercent}%</p>
            </div>
          </div>
          <div className={cx('usage-chart')}>
            <div className={cx('graph')}>
              <CircleProgressbar
                total={gpuTotal}
                used={gpuUsed}
                toolTipStyle={{ left: '-18px', top: '24px' }}
              />
            </div>
            <div className={cx('usage-text-box')}>
              <label className={cx('label')}>{t('totalGpuCount.label')}</label>
              <p className={cx('usage')}>{gpuPercent}%</p>
            </div>
          </div>
        </div>
        <div className={cx('footer')}>
          <div className={cx('items')}>
            <label className={cx(trainings > 0 && 'active')}>
              <img
                className={cx('icon')}
                src={trainings > 0 ? ActiveTrainingIcon : TrainingIcon}
                alt='trainings'
              />
              {t('trainings.label')}
            </label>
            <p className={cx('count', trainings > 0 && 'active')}>
              {trainings}
            </p>
          </div>
          <div className={cx('items')}>
            <label className={cx(deployments > 0 && 'active')}>
              <img
                className={cx('icon')}
                src={deployments > 0 ? ActiveDeploymentIcon : DeploymentIcon}
                alt='deployments'
              />
              {t('deployments.label')}
            </label>
            <p className={cx('count', deployments > 0 && 'active')}>
              {deployments}
            </p>
          </div>
          <div className={cx('items')}>
            <label className={cx(images > 0 && 'active')}>
              <img
                className={cx('icon')}
                src={images > 0 ? ActiveDockerImageIcon : DockerImageIcon}
                alt='dockerImages'
              />
              {t('dockerImages.label')}
            </label>
            <p className={cx('count', images > 0 && 'active')}>{images}</p>
          </div>
          <div className={cx('items')}>
            <label className={cx(datasets > 0 && 'active')}>
              <img
                className={cx('icon')}
                src={datasets > 0 ? ActiveDatasetIcon : DatasetIcon}
                alt='datasets'
              />
              {t('datasets.label')}
            </label>
            <p className={cx('count', datasets > 0 && 'active')}>{datasets}</p>
          </div>
        </div>
      </div>
      {status === 'expired' && (
        <div className={cx('expired-dim')}>
          <img src='/images/icon/ic-warning-red.svg' alt='Access Denied' />
          <div>{t('workspaceExpired.title')}</div>
          <div className={cx('message')}>
            {ADMIN_EMAIL
              ? `${t('workspaceExpired.message', { email: ADMIN_EMAIL })}`
                  .split('\n')
                  .map((text, i) => (
                    <p key={i}>
                      {text} <br />
                    </p>
                  ))
              : `${t('workspaceExpiredNoEmail.message', { name: manager })}`
                  .split('\n')
                  .map((text, i) => (
                    <p key={i}>
                      {text} <br />
                    </p>
                  ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default Card;
