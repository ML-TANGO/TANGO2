import { useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

import { Button, Tooltip } from '@tango/ui-react';

// Molecules
import DropMenu from '@src/components/molecules/DropMenu';
import BtnMenu from '@src/components/molecules/DropMenu/BtnMenu';
// Components
import { toast } from '@src/components/Toast';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { openModal } from '@src/store/modules/modal';
// Custom hook
import useLocalStorage from '@src/hooks/useLocalStorage';
// Network
import {
  callApi,
  STATUS_FAIL,
  STATUS_INTERNAL_SERVER_ERROR,
  STATUS_SUCCESS,
} from '@src/network';

import CallCountChart from './CallCountChart';

// Utils
import {
  copyToClipboard,
  defaultSuccessToastMessage,
  errorToastMessage,
} from '@src/utils';

// CSS Module
import classNames from 'classnames/bind';
import style from './Card.module.scss';

// Icons
import WarningIcon from '@src/static/images/icon/ic-warning-red.svg';

const cx = classNames.bind(style);
const calIcon = (type) => {
  if (type === 'Tango Intelligence')
    return '/src/static/images/icon/tango-intell.svg';
  if (type === 'Hugging Face')
    return '/src/static/images/icon/hugging-face.svg';
  return '/src/static/images/icon/00-ic-deploy-project.svg';
};

/**
 *
 * @component
 * @example
 *
 * return (
 *  <Card />
 * )
 */
function Card({ data, refreshData }) {
  const { t } = useTranslation();

  const setWorkerStatusInLocalStorage = useLocalStorage('worker_status')[1];
  const loginUserName = window.sessionStorage.getItem('user_name');

  // 컴포넌트 props
  const {
    id: deploymentId,
    deployment_name: deploymentName,
    user_name: creator,
    description,
    deployment_type: type, // 배포 타입
    built_in_model_name: builtInModelName,
    deployment_status: { status: deploymentStatus, worker },
    api_address: apiAddress,
    permission_level: permissionLevel,
    call_count_chart: CallCountChartData,
    bookmark,
    model_type: modelType,
    access,
    item_deleted,
    users,
    user_name,
    instance,
    api_address,
  } = data;

  const calCardType = (type) => {
    if (type === 'custom') return 'Custom';
    if (type === 'built-in') return 'Tango Intelligence';
    return 'Hugging Face';
  };

  const cardType = calCardType(modelType);
  const icon = calIcon(cardType);

  // 컴포넌트 State
  const [stopLoading, setStopLoading] = useState(false);
  const [isApiOpen, setIsApiOpen] = useState(false);
  // Redux Hooks
  const dispatch = useDispatch();
  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;
  const isInitialInstance =
    !instance.ram && !instance.cpu && !instance.gpu.name;
  /**
   * 자원 사용 중인 모든 액션 종료
   */
  const deploymentStop = async () => {
    setStopLoading(true);
    const response = await callApi({
      url: `deployments/stop?deployment_id=${deploymentId}`,
      method: 'get',
    });
    setStopLoading(false);
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('stop');
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
  };

  /**
   * 배포 수정 모달 열기
   */
  const deploymentEdit = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_DEPLOYMENT',
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
          deploymentId,
          workspaceId,
        },
      }),
    );
  };

  /**
   * API 호출 DELETE
   * 배포 삭제
   *
   * @param {number} deploymentId 배포 ID
   */
  const onDelete = async (deploymentId) => {
    const response = await callApi({
      url: `deployments/${deploymentId}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      refreshData();
      console.log('deployment delete success');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 배포 삭제
   */
  const deploymentDelete = () => {
    dispatch(
      openConfirm({
        title: 'deleteDeploymentPopup.title.label',
        content: 'deleteDeploymentPopup.message',
        testid: 'deployment-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete(deploymentId);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: deploymentName,
      }),
    );
  };

  /**
   * 배포 카드 북마크 설정
   */
  const bookmarkHandler = async () => {
    const body = { deployment_id: deploymentId };
    const response = await callApi({
      url: 'deployments/bookmark',
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
   * 배포 상세 페이지로 이동
   */
  const moveToDeploymentDetail = (e) => {
    e.stopPropagation();
    setWorkerStatusInLocalStorage('', true);
    sessionStorage.setItem(
      `deployment/${workspaceId}_scroll_pos`,
      window.scrollY,
    );
    if (permissionLevel > 4) return;
    if (!e.target.closest('button') && !e.target.closest('.event-block')) {
      if (worker.count === 0) {
        // 워커가 없을 때 워커 페이지로 이동
        history.push(
          `/user/workspace/${workspaceId}/deployments/${deploymentId}/workers`,
        );
      } else {
        // 워커가 있을 때 대시보드 페이지로 이동
        history.push(
          `/user/workspace/${workspaceId}/deployments/${deploymentId}/dashboard`,
        );
      }
    }
  };
  const isValidAccess = permissionLevel < 5;

  const isWorkingStatus =
    deploymentStatus === 'pending' || deploymentStatus === 'running';

  // 배포 카드 컨텍스트 팝업에 들어갈 버튼 목록
  const btnList = [
    {
      name: t('stop.label'),
      iconPath: '/images/icon/00-ic-basic-stop-o-black.svg',
      onClick: deploymentStop,
      disable: !isValidAccess || !isWorkingStatus,
      testId: 'deployment-stop-btn',
    },
    {
      name: t('edit.label'),
      iconPath: '/images/icon/00-ic-basic-pen.svg',
      onClick: deploymentEdit,
      testId: 'deployment-edit-btn',
      disable: !isValidAccess || deploymentStatus === 'running',
    },
  ];
  const gpuContentRender = () => {
    if (instance?.type === 'NPU') {
      if (!instance?.npu?.name) return '-';
      if (!instance.npu.count) return instance.npu.nmae;
      return instance.npu.name.length < 25
        ? `${instance.npu.name} x ${instance.npu.count}EA`
        : `${instance.npu.name.slice(0, 22)}... x ${instance.npu.count}EA`;
    } else if (instance?.gpu?.name) {
      return instance.gpu.name.length < 30
        ? `${instance.gpu.name} x ${instance.gpu.count}EA`
        : `${instance.gpu.name.slice(0, 27)}... x ${instance.gpu.count}EA`;
    } else {
      return '-';
    }
  };
  const gpuContentFullRender = () => {
    if (instance?.type === 'NPU') {
      if (!instance?.npu?.name) return '-';
      if (!instance.npu.count) return instance.npu.nmae;
      return `${instance.npu.name} x ${instance.npu.count}EA`;
    } else if (instance?.gpu?.name) {
      return `${instance.gpu.name} x ${instance.gpu.count}EA`;
    } else {
      return '-';
    }
  };

  return (
    <div
      className={cx(
        'card',
        permissionLevel > 4 && 'disabled',
        deploymentStatus,
      )}
      onClick={moveToDeploymentDetail}
    >
      {permissionLevel > 4 && <div className={cx('dim')}></div>}
      {/* {deploymentStatus && (
        <div
          className={cx(
            'active-bar',
            deploymentStatus,
            stopLoading && 'loading',
          )}
        ></div>
      )} */}
      <div className={cx('header')}>
        <div className={cx('deployment-type')}>
          {type === 'built-in' ? (
            <>
              {item_deleted.length > 0 && (
                <span className={cx('tooltip-error')}>
                  <Tooltip
                    title={t('template.deployment.warning.Tooltip.message')}
                    contents={
                      <ul className={cx('tooltip-error-list')}>
                        {Array.isArray(item_deleted) && item_deleted.map((item, idx) => (
                          <li key={idx}>{t(item)}</li>
                        ))}
                      </ul>
                    }
                    contentsAlign={{
                      vertical: 'bottom',
                      horizontal: 'left',
                    }}
                    customStyle={{
                      position: 'relative',
                      display: 'block',
                    }}
                  >
                    <img src={WarningIcon} alt='error' />
                  </Tooltip>
                </span>
              )}
              {builtInModelName || t('deleteDeploymentModelInfo.label')}
            </>
          ) : (
            <span
              className={cx(
                'text',
                deploymentStatus === 'running' ? 'running' : 'normal',
                'custom-text',
              )}
            >
              <img
                className={cx('icon', deploymentStatus !== 'running' && 'gray')}
                src={icon}
                alt='Custom'
              />
              <span
                className={cx(
                  'cardType',
                  deploymentStatus === 'running' && 'blue',
                )}
              >
                {cardType}
              </span>
            </span>
          )}
        </div>
        <div className={`${cx('popup-wrap')} event-block`}>
          <img
            src='/images/icon/00-ic-new-delete.svg'
            alt='delete'
            onClick={() => {
              if (!isValidAccess) return;
              deploymentDelete();
            }}
          />
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

          <div
            className={cx('bookmark', bookmark === 1 && 'marked')}
            onClick={bookmarkHandler}
            name={t('bookmark.label')}
          ></div>
        </div>
      </div>
      <div className={cx('contents')}>
        <div>
          <div className={cx('deployment-info')}>
            <div className={cx('deployment-creator')}>
              <span className={cx('creator')}>{creator}</span>
              {access === 0 && (
                <span className={cx('auth')}>
                  <img
                    src='/images/icon/00-ic-info-lock.svg'
                    alt='private icon'
                  />
                </span>
              )}
            </div>
            <div className={cx('deploy-name-box')}>
              <div className={cx('deployment-name')}>{deploymentName}</div>
              {/* <p className={cx('deployment-desc')}>{description}</p> */}
              {description && (
                <Tooltip
                  contents={description}
                  customStyle={{
                    display: 'block',
                    marginLeft: '4px',
                    marginTop: '4px',
                  }}
                  contentsAlign={{
                    horizontal: deploymentName.length > 5 ? 'center' : 'left',
                  }}
                >
                  <img
                    src='/images/icon/ic-description.svg'
                    alt='description'
                  />
                </Tooltip>
              )}
            </div>

            <div className={cx('inner-box')}>
              <div className={cx('title')}>{t('instanceName.label')}</div>
              <div className={cx('name')}>
                {instance.name
                  ? ` ${instance.name} x ${instance.allocate}EA`
                  : '-'}
              </div>
            </div>
          </div>
          <div className={cx('line')}></div>
          <div className={cx('instance')}>
            <div className={cx('title')}>
              {t('instanceConfiguration.label')}
            </div>
            {isInitialInstance && (
              <div className={cx('empty-instance')}>
                {t('instance.reallocation.desc')}
              </div>
            )}
            {!isInitialInstance && (
              <>
                <div className={cx('info')}>
                  <span className={cx('resource')}>
                    {instance?.type === 'NPU' ? 'vNPU' : 'vGPU'}
                  </span>
                  <span
                    data-fullname={gpuContentFullRender()}
                    className={cx('vgpu')}
                  >
                    {gpuContentRender()}
                  </span>
                </div>
                <div className={cx('info')}>
                  <span className={cx('resource')}>vCPU</span>
                  <span className={cx('detail')}>
                    {instance.cpu ? `${instance.cpu} Cores` : '-'}{' '}
                  </span>
                </div>
                <div className={cx('info')}>
                  <span className={cx('resource')}>RAM</span>
                  <span className={cx('detail', 'ram')}>
                    {instance.ram ? `${instance.ram} GB` : '-'}
                  </span>
                </div>
              </>
            )}
          </div>
          {/* <div className={`${cx('deployment-detail')} event-block`}>
            {worker.count > 0 && <WorkerStatus worker={worker} />}
            {apiAddress && <Api apiAddress={apiAddress} />}
          </div> */}
        </div>
        <CallCountChart data={CallCountChartData} />
        <div className={cx('api-container')}>
          {isApiOpen && apiAddress && (
            <div
              className={cx('api-copy')}
              onClick={(e) => {
                e.stopPropagation();
              }}
            >
              <span className={cx('title')}>API 주소</span>
              <div className={cx('api')}>
                {`${window.location.origin}${apiAddress}`.slice(0, 33)}...
                <img
                  src='/images/icon/00-ic-basic-copy-o.svg'
                  alt='copy'
                  width={20}
                  height={20}
                  onClick={(e) => {
                    copyToClipboard(`${window.location.origin}${apiAddress}`);
                    toast.success('API 주소가 복사되었습니다.');
                    e.stopPropagation();
                  }}
                />
              </div>
            </div>
          )}
          <button
            className={cx('api-btn', apiAddress ? 'active' : 'normal')}
            onClick={() => setIsApiOpen((prev) => !prev)}
          >
            API
          </button>
        </div>
      </div>
    </div>
  );
}

export default Card;
