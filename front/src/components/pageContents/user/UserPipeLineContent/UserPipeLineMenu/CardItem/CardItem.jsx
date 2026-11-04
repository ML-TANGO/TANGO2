import React from 'react';
import { useTranslation } from 'react-i18next';

import { addNineHours } from '@src/utils';

import classNames from 'classnames/bind';
import style from './CardItem.module.scss';

import IconBookMarkActive from '@src/static/images/icon/00-ic-basic-bookmark-o.svg';
import IconBookMark from '@src/static/images/icon/00-ic-basic-bookmark.svg';
import IconLock from '@src/static/images/icon/00-ic-info-lock.svg';
import IconEdit from '@src/static/images/icon/00-new-edit.svg';
import IconTrash from '@src/static/images/icon/00-new-trash.svg';

const cx = classNames.bind(style);

export default function CardItem({
  id,
  title,
  subTitle,
  constructor,
  retraining_wait_start_time,
  runningTime,
  createTime,
  status,
  isBookMark,
  isAccess,
  private_user_list,
  handleBookMark,
  handleOnClickCard,
  handleDelete,
  handleEdit,
  width,
  height,
}) {
  const { t } = useTranslation();
  return (
    <div
      className={cx('card-cont', status && status !== 'stop' && 'active')}
      onClick={(e) => handleOnClickCard(e, id, constructor)}
      style={{ width, height }}
    >
      <div className={cx('top-cont')}>
        <div className={cx('owner-cont')}>
          <span className={cx('owner-txt')}>{constructor}</span>
          {!isAccess && <img src={IconLock} alt='lock' />}
        </div>
        <div className={cx('btn-cont')}>
          {handleDelete && (
            <button
              className={cx('star-btn')}
              onClick={(e) =>
                handleDelete(
                  e,
                  id,
                  title,
                  isAccess,
                  constructor,
                  private_user_list,
                )
              }
            >
              <img className={cx('img')} src={IconTrash} alt='trash-btn' />
            </button>
          )}
          {handleEdit && (
            <button
              className={cx('edit-btn')}
              onClick={(e) =>
                handleEdit(
                  e,
                  title,
                  id,
                  subTitle,
                  constructor,
                  isAccess,
                  private_user_list,
                )
              }
            >
              <img className={cx('img')} src={IconEdit} alt='edit-btn' />
            </button>
          )}
          {handleBookMark && (
            <button
              className={cx('trash-btn')}
              onClick={(e) => handleBookMark(e, id, isBookMark)}
            >
              <img
                className={cx('img')}
                src={isBookMark ? IconBookMarkActive : IconBookMark}
                alt='star-btn'
              />
            </button>
          )}
        </div>
      </div>
      <h3 className={cx('title')}>{title && title}</h3>
      <span className={cx('create-time-txt')}>
        {addNineHours(createTime ?? '')}
      </span>
      <div className={cx('content', !subTitle && 'noDesc')}>
        {subTitle ? subTitle : t('no.desc')}
      </div>
      <div className={cx('update-cont')}>
        <span className={cx('update-label-txt')}>실행 경과 시간</span>
        <span className={cx('update-time-txt')}>{runningTime ?? '-'}</span>
      </div>
      <div className={cx('update-cont')}>
        <span className={cx('update-label-txt')}>
          다음 업데이트까지 잔여 시간
        </span>
        <span className={cx('update-time-txt')}>
          {retraining_wait_start_time ?? '-'}
        </span>
      </div>
    </div>
  );
}
