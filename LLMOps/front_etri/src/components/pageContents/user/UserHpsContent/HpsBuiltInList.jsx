import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { calcDuration, getKoreaTime } from '@src/datetimeUtils';

import ProcessToolTip from '@src/components/Modal/AddDatasetPreprocess/ProcessToolTip';

import { openConfirm } from '@src/store/modules/confirm';
import { closeModal, openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import GrayArrowClose from '/images/icon/gray-close-arrow.svg';
import GrayArrowOpen from '/images/icon/gray-open-arrow.svg';
import GrayPaperIcon from '/images/icon/gray-paper.svg';
import StopIcon from '/images/icon/gray-stop.svg';
import TrashIcon from '/images/icon/gray-trash.svg';
import OrangePaperIcon from '/images/icon/orange-paper.svg';
import ErrorIcon from '/images/icon/yellow-error.svg';

import classNames from 'classnames/bind';
import style from './HpsBuiltInList.module.scss';

const cx = classNames.bind(style);

const STATUS_TEXT = {
  pending: '대기',
  done: '종료',
  running: '진행',
  error: '오류',
  installing: '설치중',
  stop: '중지',
};

const HpsBuiltInList = ({
  id,
  name,
  createAt,
  dataset,
  startAt,
  gpu,
  parameter,
  status,
  isAllOpen,
  dataPath,
  searchCount,
  isResult,
  endAt,
  handleResultModal,
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [isOpen, setIsOpen] = useState(true);

  const openLogModal = (id) => {
    if (status === 'pending') return;

    dispatch(
      openModal({
        modalType: 'HPS_LOG',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('HPS_LOG'));
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          id,
          status,
          name,
        },
      }),
    );
  };

  const deleteTool = async () => {
    const response = await callApi({
      url: 'projects/hps',
      method: 'delete',
      body: {
        hps_id_list: [id],
      },
    });
  };

  const stopTool = async () => {
    const { status, message, error } = await callApi({
      url: `projects/hps/stop?hps_id=${id}`,
      method: 'get',
    });
  };

  const deleteToolConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'HPS 삭제',
        content: 'deleteJobPopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            deleteTool();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        notice: t('deleteJobPopup.notice.message'),
        contentCustomStyle: {
          color: 'rgba(116, 116, 116, 1)',
        },
      }),
    );
  };

  useEffect(() => {
    setIsOpen(isAllOpen); // 부모의 isAllOpen 값에 따라 상태 업데이트
  }, [isAllOpen]);

  return (
    <div className={cx('container')}>
      <div className={cx('basic-info', isOpen && 'open')}>
        <img
          className={cx('arrow')}
          onClick={() => setIsOpen((prev) => !prev)}
          width={24}
          height={24}
          src={isOpen ? GrayArrowOpen : GrayArrowClose}
          alt='arrow'
        />
        <span
          onClick={() => openLogModal(id)}
          className={cx('system-log', status === 'pending' && 'disabled')}
        >
          시스템 로그
        </span>
        <div className={cx('info-box')}>
          <div className={cx('first-info')}>
            <div className={cx('status', status)}>{STATUS_TEXT[status]}</div>
            <div className={cx('detail')}>
              <span className={cx('name')}>{name}</span>
              <span className={cx('time')}>{getKoreaTime(createAt)}</span>
            </div>
          </div>

          <div className={cx('detail')}>
            <span className={cx('type')}>데이터셋</span>
            <span className={cx('value')}>{dataset}</span>
          </div>
          <div className={cx('detail')}>
            <span className={cx('type')}>데이터</span>
            <span className={cx('value')}>
              {dataPath.length < 50 ? dataPath : `${dataPath.slice(0, 47)}...`}
            </span>
          </div>
          <div className={cx('btn-box')}>
            {status === 'error' && (
              <ProcessToolTip
                icon={ErrorIcon}
                iconHeight={24}
                iconWidth={24}
                position={'down'}
                iconStyle={{ transform: 'translateY(2px)' }}
                customStyle={{
                  height: '80px',
                  width: '305px',
                  padding: '16px',
                  transform: 'translate(-240px, 10px)',
                }}
                contents={
                  <div className={cx('tool-tip-content')}>
                    <span>학습 환경 구성 중 오류가 발생했습니다.</span>
                  </div>
                }
              />
            )}

            <div
              className={cx(
                'process-download-btn',
                status === 'done' && isResult && 'orange',
              )}
              onClick={() => {
                if (status === 'done' && isResult) {
                  handleResultModal(id);
                }
              }}
            >
              <img
                src={
                  status === 'done' && isResult
                    ? OrangePaperIcon
                    : GrayPaperIcon
                }
                alt='icon'
              />
              <span>학습 결과</span>
            </div>

            <img
              className={cx('trash-btn')}
              width={24}
              height={24}
              src={TrashIcon}
              alt='trash'
              onClick={deleteToolConfirmPopup}
            />
          </div>
        </div>
      </div>
      {isOpen && (
        <div className={cx('detail-info')}>
          <div className={cx('stop-btn-box')}>
            {status === 'running' && (
              <img
                className={cx('stop-btn')}
                width={20}
                height={20}
                src={StopIcon}
                alt='stop'
                onClick={stopTool}
              />
            )}
          </div>
          <div className={cx('info-box')}>
            {status === 'pending' && (
              <div className={cx('pending-ui')}>
                <img
                  src='/images/icon/00-ic-orange-history.svg'
                  alt='history'
                  width={16}
                  height={16}
                />
                <span>학습을 실행하기 위한 GPU 자원 할당 대기 중입니다.</span>
              </div>
            )}
            {status !== 'pending' && (
              <div className={cx('detail', 'first-detail')}>
                <span className={cx('type')}>학습 실행 시간</span>
                <span className={cx('value')}>
                  {status === 'done' ? (
                    <span>
                      {`${getKoreaTime(startAt)} ~ ${getKoreaTime(endAt)}`}
                      <br />
                      <span className={cx('duration')}>
                        {calcDuration(startAt, endAt)}
                      </span>
                    </span>
                  ) : (
                    `${getKoreaTime(startAt)} ~ `
                  )}
                </span>
              </div>
            )}

            <div className={cx('detail')}>
              <span className={cx('type')}>GPU 할당</span>
              <span className={cx('value')}>{gpu} EA</span>
            </div>
            <div className={cx('detail', 'long-detail')}>
              <span className={cx('type')}>검색 횟수</span>
              <span className={cx('value')}>{searchCount}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HpsBuiltInList;
