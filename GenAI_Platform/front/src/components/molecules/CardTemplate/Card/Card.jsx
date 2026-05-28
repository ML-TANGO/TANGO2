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
