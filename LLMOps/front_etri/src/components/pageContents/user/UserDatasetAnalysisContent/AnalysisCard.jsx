import React from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';

import classNames from 'classnames/bind';
import style from './AnalysisCard.module.scss';

const cx = classNames.bind(style);

const AnalysisCard = ({
  owner,
  name,
  desc,
  cpu,
  gpu,
  ram,
  instanceName,
  id,
  deleteAnalysis,
  fetchProcessList,
  instanceAllocate,
  access,
  handleBookMark,
  isBookMark,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const { id: wid } = useParams();

  const handleModifyModal = () => {
    dispatch(
      openModal({
        modalType: 'ADD_DATASET_ANALYSIS',
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
          modalType: 'EDIT_DATASET_ANALYSIS',
        },
      }),
    );
  };

  const analysisDelete = () => {
    dispatch(
      openConfirm({
        title: 'analysisDeletePopup.title.label',
        content: 'analysisDeletePopup.message',
        testid: 'process-delete-modal',
        submit: {
          text: 'delete.label',
          func: () => {
            deleteAnalysis(id);
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: name,
      }),
    );
  };

  return (
    <div
      className={cx('card-container')}
      onClick={() =>
        history.push(`/user/workspace/${wid}/datasets/analysis/${id}/detail`)
      }
    >
      <div className={cx('header')}>
        <span className={cx('owner')}>{owner}</span>
        <div className={cx('tools')}>
          <div
            className={cx('delete-icon')}
            onClick={(e) => {
              analysisDelete();
              e.stopPropagation();
            }}
          >
            <img
              width={24}
              height={24}
              src='/images/icon/00-ic-new-delete.svg'
              alt='delete'
            />
          </div>

          <div
            className={cx('pen-icon')}
            onClick={(e) => {
              handleModifyModal();
              e.stopPropagation();
            }}
          >
            <img
              width={24}
              height={24}
              src={'/src/static/images/icon/00-new-edit.svg'}
              alt='pencil'
            />
          </div>
          <div name={t('bookmark.label')} className={cx('bookmark')}>
            <img
              className={cx('img')}
              src={
                isBookMark
                  ? '/src/static/images/icon/00-ic-basic-bookmark-o.svg'
                  : '/src/static/images/icon/00-ic-basic-bookmark.svg'
              }
              onClick={(e) => handleBookMark(e, id, isBookMark)}
              alt='star-btn'
            />
          </div>
        </div>
      </div>
      <div className={cx('name')}>{name}</div>
      <div className={cx('desc')}>{desc}</div>
      <div className={cx('instance-title')}>
        {t('instanceConfiguration.label')}
      </div>
      {instanceName ? (
        <div className={cx('info')}>
          <div className={cx('detail')}>
            <div className={cx('type')}>vGPU</div>
            <div className={cx('value')}>
              {instanceAllocate
                ? `${instanceName} x ${instanceAllocate} EA`
                : '-'}
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
          {t('instance.reallocation.desc')}
        </div>
      )}
    </div>
  );
};

export default AnalysisCard;
