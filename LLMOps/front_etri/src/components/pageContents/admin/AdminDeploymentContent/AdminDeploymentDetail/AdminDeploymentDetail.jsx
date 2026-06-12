// Utils
import { ButtonV2 } from '@tango/ui-react';

import { convertLocalTime } from '@src/datetimeUtils';
import warningIcon from '@src/static/images/icon/ic-warning-yellow-white.svg';
import { Fragment, useEffect, useState } from 'react';
import { CopyToClipboard } from 'react-copy-to-clipboard';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

// Components
import Tooltip from '@src/components/atoms/Tooltip';
import Table from '@src/components/molecules/BorderTable/Table';
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDeploymentDetail.module.scss';

const cx = classNames.bind(style);

const AdminDeploymentDetail = ({ data, onRefresh }) => {
  // 임시 주석
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const {
    id: deploymentId,
    deployment_name: deploymentName,
    description,
    access,
    users,
    create_datetime: createdDatetime,
    deployment_worker_list: workerList,
    api_address: apiAddress,
    instance,
  } = data;
  const gpuName = instance?.instance_info?.gpu_name || '-';
  const [detailTableData, setDetailTableData] = useState([]);
  const userList = users?.map(({ user_name: user }) => {
    return user;
  });

  const columns = [
    {
      name: t('name.label'),
      selector: 'id',
      minWidth: '120px',
      maxWidth: '140px',
      cell: ({ id }) => {
        return `${t('worker.label')} ${id}`;
      },
    },
    {
      name: t('status.label'),
      selector: 'status',
      minWidth: '60px',
      maxWidth: '90px',
      cell: ({ status, status_reason: reason }) => {
        return (
          <>
            {t(status)}
            <Tooltip
              contents={
                <div className={cx('tooltip-wrapper')}>
                  <div className={cx('tooltip')}>{reason || '-'}</div>
                </div>
              }
              icon={warningIcon}
              iconCustomStyle={{
                marginLeft: '4px',
              }}
              contentsCustomStyle={{
                border: '0.5px solid #DEE9FF',
                borderRadius: '10px',
                boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                padding: '16px',
              }}
            />
          </>
        );
      },
    },
    {
      name: t('configurations.label'),
      selector: 'configurations',
      minWidth: '500px',
      cell: ({ configurations_resource: resource }) => {
        const { cpu, gpu, ram } = resource;
        return (
          <div className={cx('config')}>
            <div className={cx('item')}>
              <span className={cx('label')}>vGPU</span>
              <span>{gpuName}</span>
            </div>
            <div className={cx('item')}>
              <span className={cx('label')}>vCPU</span>
              <span>{cpu ?? '-'} Cores</span>
            </div>
            <div className={cx('item')}>
              <span className={cx('label')}>RAM</span>
              <span>{ram ?? '-'} GB</span>
            </div>
          </div>
        );
      },
    },
    {
      name: t('description.label'),
      selector: 'description',
      minWidth: '80px',
      cell: ({ description }) => {
        return description ?? '-';
      },
    },
    {
      name: t('createdDatetime.label'),
      selector: 'create_datetime',
      minWidth: '90px',
      maxWidth: '180px',
    },
    {
      name: t('stop.label'),
      minWidth: '120px',
      cell: ({ id }) => {
        return (
          <ButtonV2
            label={t('stopAll.label')}
            size='l'
            colorType='lightRed'
            onClick={() => {
              onStopWorker(id);
            }}
          />
        );
      },
      button: true,
    },
  ];

  /**
   * 워커 중지
   *
   * @param {number} id worker ID
   */
  const onStopWorker = async (id) => {
    const response = await callApi({
      url: `deployments/worker/stop?deployment_worker_id=${id}`,
      method: 'GET',
    });
    const { status, message } = response;
    if (status === STATUS_SUCCESS) {
      toast.success(t('workerStop.toast.message', { worker: id }));
    } else {
      toast.error(message);
    }
    setTimeout(() => {
      onRefresh();
    }, 1000);
  };

  const onCopy = () => {
    toast.success(t('copyToClipboard.success.message'));
  };

  /**
   * API 수정 모달 오픈
   */
  // const openEditApiModal = () => {
  //   dispatch(
  //     openModal({
  //       modalType: 'EDIT_API',
  //       modalData: {
  //         submit: {
  //           text: t('edit.label'),
  //           func: () => {
  //             dispatch(closeModal('EDIT_API'));
  //           },
  //         },
  //         cancel: {
  //           text: t('cancel.label'),
  //         },
  //         deploymentId,
  //         apiAddress,
  //       },
  //     }),
  //   );
  // };

  useEffect(() => {
    setDetailTableData(workerList);
  }, [workerList]);

  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <div className={cx('title')}>
          <span>{deploymentName}</span>
          <span>{t('detailsOf')}</span>
        </div>
        <p className={cx('desc')}>{description}</p>
      </div>
      <div className={cx('horizon-box')}>
        <div className={cx('box')}>
          <span className={cx('label')}>{t('createdDatetime.label')}</span>
          <span className={cx('value')}>
            {createdDatetime ? convertLocalTime(createdDatetime) : '-'}
          </span>
        </div>
        <div className={cx('box')}>
          <span className={cx('label')}>{t('accessType.label')}</span>
          <span className={cx('value')}>
            {access === 0 ? 'Private' : 'Public'}
          </span>
        </div>
        <div className={cx('box', 'two-column')}>
          <label className={cx('label')}>
            {t('users.label')} ({users ? users.length : 0})
          </label>
          {userList && (
            <div className={cx('value', 'user')} title={userList.join(', ')}>
              {userList.join(', ') ?? '-'}
            </div>
          )}
        </div>
      </div>
      <div className={cx('box', 'two-column')}>
        <div className={cx('label')}>{t('apiAddress.label')}</div>
        <div className={cx('value-box')}>
          <span className={cx('value')} title={apiAddress}>
            {apiAddress ?? '-'}
          </span>
          {apiAddress && (
            <Fragment>
              <CopyToClipboard text={apiAddress} onCopy={onCopy}>
                <button
                  className={cx('btn', 'copy-btn')}
                  title={t('copyToClipboard.message')}
                ></button>
              </CopyToClipboard>
              {/* <button
                  className={cx('btn', 'edit-btn')}
                  onClick={openEditApiModal}
                ></button> */}
            </Fragment>
          )}
        </div>
      </div>
      <label className={cx('table-title')}>{t('worker.label')}</label>
      <Table
        data={detailTableData}
        columns={columns}
        selectableRows={false}
        totalRows={detailTableData.length}
        defaultSortField='create_datetime'
        hideSearchBox={true}
        fixedHeader={true}
        fixedHeaderScrollHeight='200px'
      />
    </div>
  );
};

export default AdminDeploymentDetail;
