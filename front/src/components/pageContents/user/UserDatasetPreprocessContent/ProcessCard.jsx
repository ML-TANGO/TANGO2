import React from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import { getKoreaTime } from '@src/datetimeUtils';

import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';

import classNames from 'classnames/bind';
import style from './ProcessCard.module.scss';

import IconLock from '@src/static/images/icon/00-ic-info-lock.svg';

const cx = classNames.bind(style);

const ProcessCard = ({
  owner,
  name,
  desc,
  cpu,
  gpu,
  ram,
  instance,
  id,
  deleteProcess,
  fetchProcessList,
  access,
  jobStatus,
  time,
  type,
  instanceAllocate,
  isBookmark,
  bookmarkProcess,
  userList,
  loginUser,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const { id: wid } = useParams();

  const handleModifyModal = () => {
    dispatch(
      openModal({
        modalType: 'MODIFY_DATASET_PREPROCESS',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              fetchProcessList();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspace_id: wid,
          project_id: id,
        },
      }),
    );
  };

  const processDelete = () => {
    dispatch(
      openConfirm({
        title: 'processPopup.title.label',
        content: 'deleteProcessPopup.message',
        testid: 'process-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            deleteProcess(id);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: name,
      }),
    );
  };
  const usersName = userList.map(({ user_name }) => user_name);
  const isAccessValid =
    [...usersName, owner].includes(loginUser) || access === 1;

  return (
    <div
      className={cx('card-container', jobStatus, !isAccessValid && 'notAccess')}
      onClick={() => {
        if (!isAccessValid) return;
        history.push(`/user/workspace/${wid}/datasets/process/${id}/detail`);
      }}
    >
      <div className={cx('header')}>
        <span className={cx('type', jobStatus)}>
          <span>{type === 'built-in' ? 'Built-in' : 'Custom'} 전처리기</span>
          {!isAccessValid && (
            <img className={cx('lock')} src={IconLock} alt='lock' />
          )}
        </span>
        <div className={cx('tools')}>
          <div
            className={cx('delete-icon', jobStatus !== 'stop' && 'stop')}
            onClick={(e) => {
              if (jobStatus !== 'stop' || !isAccessValid) {
                e.stopPropagation();
                return;
              }
              processDelete();
              e.stopPropagation();
            }}
          >
            <img
              width={24}
              height={24}
              src={
                jobStatus === 'stop'
                  ? '/images/icon/00-ic-new-delete.svg'
                  : '/images/icon/00-ic-new-delete-light.svg'
              }
              alt='delete'
            />
          </div>
          <div
            className={cx('pen-icon')}
            onClick={(e) => {
              if (!isAccessValid) return;
              handleModifyModal();
              e.stopPropagation();
            }}
          >
            <img
              width={24}
              height={24}
              src='/src/static/images/icon/00-new-edit.svg'
              alt='pencil'
            />
          </div>
          <div name={t('bookmark.label')} className={cx('bookmark')}>
            <img
              src={
                isBookmark
                  ? '/src/static/images/icon/00-ic-basic-bookmark-o.svg'
                  : '/src/static/images/icon/00-ic-basic-bookmark.svg'
              }
              alt='bookmark'
              onClick={(e) => {
                if (!isAccessValid) return;
                bookmarkProcess(id);
                e.stopPropagation();
              }}
            />
          </div>
        </div>
      </div>
      <div className={cx('owner')}>{owner}</div>
      <div className={cx('name')} data-fullname={name}>
        {/* {name.length < 25 ? name : `${name.slice(0, 22)}...`} */}
        {name}
      </div>
      <div className={cx('time')}>{getKoreaTime(time)}</div>
      <div className={cx('desc')}>{desc}</div>
      <div className={cx('instance-title')}>
        {t('instanceConfiguration.label')}
      </div>

      {instance ? (
        <div className={cx('info')}>
          <div className={cx('detail')}>
            <div className={cx('type')}>vGPU</div>
            <div className={cx('value')}>
              {instanceAllocate ? `${instance} x ${instanceAllocate} EA` : '-'}
            </div>
          </div>
          <div className={cx('detail')}>
            <div className={cx('type')}>vCPU</div>
            <div className={cx('value')}>{cpu} Cores</div>
          </div>
          <div className={cx('detail')}>
            <div className={cx('type')}>RAM</div>
            <div className={cx('value')}>{ram} GB</div>
          </div>
        </div>
      ) : (
        <div className={cx('empty-info')}>
          전처리 수정 기능을 통해 인스턴스를 재할당해주세요.
        </div>
      )}
    </div>
  );
};

export default ProcessCard;
