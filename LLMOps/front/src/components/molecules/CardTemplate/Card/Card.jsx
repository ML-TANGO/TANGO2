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
  // 자물쇠(비공개) 표식 전용 — 원본 access 기반. isAccess 는 소비처마다 의미가 달라
  // (Model=계산된 접근가능 / Playground·Rag·Prompt=원시 access) 자물쇠 판정에 쓸 수 없다.
  // 미전달 시 기존 동작(!isAccess)으로 폴백한다.
  isPrivate,
  userList,
  handleBookMark,
  handleOnClickCard,
  handleDelete,
  handleEdit,
  width,
  height,
  statusBadge = false,
  // 상태 배지 라벨/색을 직접 지정하는 경로(opt-in).
  //   `status` 프롭은 **카드 강조(.active)와 배지 라벨을 겸한다**. 배포는 두 의미가 같아
  //   문제가 없지만(running 이면 강조도 배지도 running), 평가는 "강조는 실행 중일 때만,
  //   배지는 전 상태(대기/진행/완료/실패)"라 겸할 수 없다 — status 에 전 상태를 실으면
  //   완료·대기 카드까지 테두리가 돌고, 'active' 를 실으면 배지가 t('active') 가 된다.
  //   라벨을 주면 그 라벨로 그리고, 안 주면 기존 동작(statusBadge && t(status)) 그대로.
  statusBadgeLabel,
  statusBadgeKind,
  // opt-in — 접근 불가 카드. 목록에는 계속 보이되 회색 처리 + 진입 불가임을 시각화.
  // 클릭 자체는 그대로 핸들러로 보내 "접근 권한이 없습니다" 안내가 뜨게 한다
  // (조용히 무반응이면 고장으로 보임).
  noAccess = false,
  typeBadge,
  typeBadgeKind,
  qualifierBadge,
  qualifierBadgeKind,
}) => {
  const { t } = useTranslation();
  return (
    <button
      className={cx(
        'card-cont',
        status && status !== 'stop' && 'active',
        noAccess && 'no-access',
      )}
      onClick={(e) => handleOnClickCard(e, id, constructor, isAccess, userList)}
      style={{ width, height }}
      aria-label={`${title} 이동`}
      aria-disabled={noAccess || undefined}
      title={noAccess ? '접근 권한이 없습니다' : undefined}
    >
      <div className={cx('top-cont')}>
        <div className={cx('owner-cont')}>
          <span className={cx('owner-txt')}>{constructor}</span>
          {(isPrivate ?? !isAccess) && <img src={IconLock} alt='private' />}
          {/* 배포(D6)·평가 카드만 opt-in → Rag/Model 등 다른 소비자엔 미노출 */}
          {(statusBadgeLabel || (statusBadge && status)) && (
            <span
              className={cx(
                'status-badge',
                statusBadgeKind || STATUS_BADGE_CLASS[status] || 'pending',
              )}
            >
              {statusBadgeLabel || t(status)}
            </span>
          )}
          {typeBadge && (
            <span className={cx('type-badge', typeBadgeKind)}>{typeBadge}</span>
          )}
          {qualifierBadge && (
            <span className={cx('type-badge', qualifierBadgeKind)}>
              {qualifierBadge}
            </span>
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
