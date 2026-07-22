import { useTranslation } from 'react-i18next';

import { addNineHours } from '@src/utils';

import classNames from 'classnames/bind';
import style from './Card.module.scss';

import IconBookMarkActive from '@src/static/images/icon/00-ic-basic-bookmark-o.svg';
import IconBookMark from '@src/static/images/icon/00-ic-basic-bookmark.svg';
import IconLock from '@src/static/images/icon/00-ic-info-lock.svg';
import IconEdit from '@src/static/images/icon/00-new-edit.svg';
import IconTrash from '@src/static/images/icon/00-new-trash.svg';

const cx = classNames.bind(style);

// D6 v3 (Option A): 배포 상태 배지 색상 매핑. status 라벨은 기존 i18n(running/stop/pending) 재사용.
//   배지는 status 가 있을 때만 렌더 → status 미전달 소비자(Rag/Prompt/Model 등)엔 무영향.
const STATUS_BADGE_CLASS = {
  running: 'running',
  stop: 'stopped',
  pending: 'pending',
  error: 'error',
};

const Card = ({
  id,
  title,
  subTitle,
  constructor,
  updateTime,
  createTime,
  status,
  isBookMark,
  isAccess,
  userList,
  handleBookMark,
  handleOnClickCard,
  handleDelete,
  handleEdit,
  width,
  height,
  statusBadge = false,
  typeBadge,
  typeBadgeKind,
}) => {
  const { t } = useTranslation();
  return (
    <button
      className={cx('card-cont', status && status !== 'stop' && 'active')}
      onClick={(e) => handleOnClickCard(e, id, constructor, isAccess, userList)}
      style={{ width, height }}
      aria-label={`${title} 이동`}
    >
      <div className={cx('top-cont')}>
        <div className={cx('owner-cont')}>
          <span className={cx('owner-txt')}>{constructor}</span>
          {!isAccess && <img src={IconLock} alt='private' />}
          {/* 배포(D6) 카드만 statusBadge opt-in → Rag/Model 등 다른 소비자엔 미노출 */}
          {statusBadge && status && (
            <span
              className={cx(
                'status-badge',
                STATUS_BADGE_CLASS[status] || 'pending',
              )}
            >
              {t(status)}
            </span>
          )}
          {typeBadge && (
            <span className={cx('type-badge', typeBadgeKind)}>{typeBadge}</span>
          )}
        </div>
        <div className={cx('btn-cont')}>
          {handleDelete && (
            <button
              className={cx('star-btn')}
              onClick={(e) =>
                handleDelete(e, id, title, isAccess, userList, constructor)
              }
              aria-label={`${title} 삭제`}
            >
              <img className={cx('img')} src={IconTrash} alt='' />
            </button>
          )}
          {handleEdit && (
            <button
              className={cx('edit-btn')}
              onClick={(e) =>
                handleEdit(e, id, isAccess, userList, constructor)
              }
              alt={`${title} 수정`}
            >
              <img className={cx('img')} src={IconEdit} alt='' />
            </button>
          )}
          {handleBookMark && (
            <button
              className={cx('trash-btn')}
              onClick={(e) => handleBookMark(e, id, isBookMark)}
              aria-label={`${title} 즐겨찾기`}
            >
              <img
                className={cx('img')}
                src={isBookMark ? IconBookMarkActive : IconBookMark}
                alt=''
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
        <span className={cx('update-label-txt')}>
          {t('lastUpdatedTime.label')}
        </span>
        {updateTime && (
          <span className={cx('update-time-txt')}>
            {addNineHours(updateTime ?? '')}
          </span>
        )}
      </div>
    </button>
  );
};

export default Card;
