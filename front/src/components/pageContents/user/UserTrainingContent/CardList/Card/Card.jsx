// Components
import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { Button, Tooltip } from '@jonathan/ui-react';

import DropMenu from '@src/components/molecules/DropMenu';
import BtnMenu from '@src/components/molecules/DropMenu/BtnMenu';
import { toast } from '@src/components/Toast';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { openModal } from '@src/store/modules/modal';
// Network
import {
  callApi,
  STATUS_FAIL,
  STATUS_INTERNAL_SERVER_ERROR,
  STATUS_SUCCESS,
} from '@src/network';

import JobStatusBar from './JobStatusBar';
import Resource from './Resource';
import Workbench from './Workbench';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './Card.module.scss';

const cx = classNames.bind(style);

const IS_HIDE_JOB = import.meta.env.VITE_REACT_APP_IS_HIDE_JOB === 'true';
const IS_HIDE_HPS = import.meta.env.VITE_REACT_APP_IS_HIDE_HPS === 'true';

/**
 *
 * @component
 * @example
 *
 * return (
 *  <Card />
 * )
 */

const calIcon = (type) => {
  if (type === 'Jonathan Intelligence')
    return '/src/static/images/icon/jonathan-intell.svg';
  if (type === 'Hugging Face')
    return '/src/static/images/icon/hugging-face.svg';
  return '/src/static/images/icon/00-ic-deploy-project.svg';
};

function Card({ data, refreshData }) {
  const { t } = useTranslation();
  const loginUserName = window.sessionStorage.getItem('user_name');

  // 컴포넌트 props
  const {
    id: trainingId,
    name: projectName,
    create_user_name: creator,
    description,
    type, // 학습 타입
    built_in_model_name: builtInModelName,
    built_in_model,
    category,
    permission_level: permissionLevel,
    job_status: jobStatus,
    item_progress: latestItemStatus,
    status,
    tools: toolList,
    bookmark,
    access,
    instance_name: instanceName,
    instance_info: instanceInfo,
    instance_allocate: instanceAllocate,
    resource_name: resourceName,
    users,
    gpu_allocate: gpu,
    create_user_name,
  } = data;

  const calCardType = (type) => {
    if (type === 'advanced') return 'Custom';
    if (type === 'built-in') return 'Jonathan Intelligence';
    return 'Hugging Face';
  };
  const cardType = calCardType(type);
  const icon = calIcon(cardType);

  // 컴포넌트 State
  const [stopLoading, setStopLoading] = useState(false);
  // Redux Hooks
  const dispatch = useDispatch();
  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;
  const isInitialInstance =
    !resourceName && !instanceInfo.cpu_allocate && !instanceInfo.ram_allocate;
  /**
   * 자원 사용 중인 모든 액션 종료
   */
  const trainingStop = async () => {
    setStopLoading(true);
    const response = await callApi({
      url: 'projects/stop',
      method: 'post',
      body: {
        project_id: trainingId,
      },
    });
    setStopLoading(false);
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      console.log('stop success');
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
  };

  /**
   * 학습 수정 모달 열기
   */
  const trainingEdit = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_TRAINING',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              refreshData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data,
          workspaceId,
        },
      }),
    );
  };

  /**
   * API 호출 DELETE
   * 학습 삭제
   *
   * @param {number} tId 학습 ID
   */
  const onDelete = async (tId) => {
    const response = await callApi({
      url: `projects`,
      method: 'delete',
      body: {
        id_list: [tId],
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      refreshData();
      console.log('delete success');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 학습 삭제
   */
  const trainingDelete = (isValidAccess) => {
    if (!isValidAccess) return;

    dispatch(
      openConfirm({
        title: 'deleteTrainingPopup.title.label',
        content: 'deleteTrainingPopup.message',
        testid: 'training-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete(trainingId);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: projectName,
      }),
    );
  };

  /**
   * 학습 카드 북마크 설정
   */
  const bookmarkHandler = () => {
    const body = { project_id: trainingId };
    const response = callApi({
      url: 'projects/bookmark',
      method: bookmark === 0 ? 'post' : 'delete',
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      refreshData();
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else if (status === STATUS_INTERNAL_SERVER_ERROR) {
      toast.error(message);
    }
  };

  /**
   * 학습 상세 페이지(workbench)로 이동
   */
  const moveToTrainingDetail = (e) => {
    e.stopPropagation();
    sessionStorage.setItem(
      `training/${workspaceId}_scroll_pos`,
      window.scrollY,
    );
    if (permissionLevel > 4) return;
    if (!e.target.closest('button') && !e.target.closest('.event-block')) {
      if (type === 'federated-learning') {
        // 연합 학습 페이지로 이동
        history.push(
          `/user/workspace/${workspaceId}/trainings/${trainingId}/federated-learning`,
        );
      } else {
        history.push(
          `/user/workspace/${workspaceId}/trainings/${trainingId}/workbench`,
        );
      }
    }
  };
  const isActive = status.training === 'running';

  const isValidAccess = permissionLevel < 5;

  const isStatusStop =
    status.training === 'stop' && status.workbench === 'stop';

  // 학습 카드 컨텍스트 팝업에 들어갈 버튼 목록
  const btnList = [
    {
      name: t('stop.label'),
      iconPath: '/images/icon/00-ic-basic-stop-o-black.svg',
      onClick: trainingStop,
      testId: 'training-stop-btn',
      disable: !isValidAccess || isStatusStop,
    },
    {
      name: t('edit.label'),
      iconPath: '/images/icon/00-ic-basic-pen.svg',
      onClick: trainingEdit,
      testId: 'training-edit-btn',
      disable: !isValidAccess,
    },
  ];

  return (
    <div
      className={cx('card', permissionLevel > 4 && 'disabled', status.training)}
      onClick={moveToTrainingDetail}
    >
      {permissionLevel > 4 && <div className={cx('dim')}></div>}
      <div className={cx('header')}>
        <div className={cx('training-type')}>
          <div
            className={cx(
              'active-status',
              isActive && 'active',
              stopLoading && 'stop',
              permissionLevel > 4 && 'not-allowed',
            )}
          >
            {type === 'federated-learning' ? (
              <img
                className={cx('type-icon', 'built-in')}
                src='/images/icon/ic-built-in-blue.svg'
                alt='Built-in'
              />
            ) : (
              <>
                <div className={cx('custom-text')}>
                  <img
                    className={cx('icon', !isActive && 'gray')}
                    src={icon}
                    alt='Custom'
                  />
                  <span className={cx('cardType', isActive && 'blue')}>
                    {cardType}
                  </span>
                </div>
              </>
            )}
          </div>
          {/* {type === 'built-in' && (
            <span className={cx('model-name')}>
              {builtInModelName || (
                <div className={cx('deleted')}>
                  <img
                    src='/images/icon/ic-warning-red.svg'
                    alt='Deleted Model'
                  />
                  <span>{t('modelDeleted.message')}</span>
                </div>
              )}
            </span>
          )} */}
          {type === 'federated-learning' && (
            <span className={cx('model-name')}>
              {t('federatedLearning.label')}
            </span>
          )}
        </div>

        <div className={`${cx('popup-wrap')} event-block`}>
          <div className={cx('delete-icon')}>
            <img
              onClick={() => trainingDelete(isValidAccess)}
              src='/images/icon/00-ic-new-delete.svg'
              alt='delete'
            />
          </div>

          <DropMenu
            btnRender={() => (
              <Button
                type='none-border'
                size='small'
                iconAlign='left'
                icon='/images/icon/00-ic-basic-ellipsis.svg'
                iconStyle={{ margin: '0', width: '24px', height: '24px' }}
                customStyle={{
                  width: '30px',
                  padding: '6px',
                }}
                testId='card-menu-btn'
              />
            )}
            menuRender={(popupHandler) => (
              <BtnMenu btnList={btnList} callback={popupHandler} />
            )}
            align='RIGHT'
          />
          {/* 북마크 */}
          {bookmark === 1 ? (
            <div name={t('bookmark.label')} className={cx('active-bookmark')}>
              <img
                src='/images/icon/00-ic-new-bookmark-o-gray.svg'
                alt='bookmark'
                onClick={bookmarkHandler}
              />
            </div>
          ) : (
            <div
              className={cx('bookmark')}
              onClick={bookmarkHandler}
              name={t('bookmark.label')}
            ></div>
          )}
        </div>
      </div>
      <div className={cx('training-info')}>
        <div className={cx('creator-auth')}>
          <span className={cx('creator')}>{creator}</span>
          {access === 0 && (
            <span className={cx('auth')}>
              <img src='/images/icon/00-ic-info-lock.svg' alt='private icon' />
            </span>
          )}
        </div>
        <div className={cx('training-name-box')}>
          <div className={cx('training-name')}>{projectName}</div>
          {description && (
            <Tooltip
              contents={description}
              customStyle={{
                display: 'block',
                marginLeft: '4px',
                marginTop: '4px',
              }}
              contentsAlign={{
                horizontal: projectName.length > 5 ? 'center' : 'left',
              }}
            >
              <img src='/images/icon/ic-description.svg' alt='description' />
            </Tooltip>
          )}
        </div>
        <div className={cx('instance-box')}>
          <div className={cx('inner-box')}>
            <div className={cx('title')}>{t('instanceName.label')}</div>
            <div className={cx('name')}>
              {instanceName ? ` ${instanceName} x ${instanceAllocate}EA` : '-'}
            </div>
          </div>
          <div className={cx('line')}></div>
          <div className={cx('inner-box')}>
            <div className={cx('title')}>
              {t('instanceConfiguration.label')}
            </div>
            <div className={cx('configuration-box')}>
              {isInitialInstance && (
                <div className={cx('empty-instance')}>
                  {t('instance.reallocation.desc')}
                </div>
              )}
              {!isInitialInstance && (
                <>
                  <div className={cx('configuration')}>
                    <div className={cx('resource')}>vGPU</div>
                    <div title={`${resourceName} x${gpu}EA`}>
                      {resourceName && gpu ? `${resourceName} x${gpu}EA` : '-'}
                    </div>
                  </div>
                  <div className={cx('configuration')}>
                    <div className={cx('resource')}>vCPU </div>
                    <div>
                      {instanceInfo?.cpu_allocate
                        ? `${instanceInfo.cpu_allocate} Cores`
                        : '-'}
                    </div>
                  </div>
                  <div className={cx('configuration')}>
                    <div className={cx('resource')}>RAM </div>
                    <div>
                      {instanceInfo?.ram_allocate
                        ? `${instanceInfo.ram_allocate} GB`
                        : '-'}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
      {type !== 'federated-learning' && (
        <div className={cx('training-status')}>
          {/* {(!IS_HIDE_JOB || !IS_HIDE_HPS) && (
            <JobStatusBar
              trainingId={trainingId}
              trainingName={trainingName}
              jobStatus={jobStatus}
              latestItemStatus={latestItemStatus}
            />
          )} */}
          <div className={cx('btn-box')}>
            <Workbench toolList={toolList} />
            {/* <Resource resourceInfo={resourceInfo} /> */}
          </div>
        </div>
      )}
    </div>
  );
}

export default Card;
