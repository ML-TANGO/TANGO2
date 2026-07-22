import classNames from 'classnames/bind';
import style from './DeployDetailHeader.module.scss';

const cx = classNames.bind(style);

// 배포 상세(온디바이스/standalone) 공용 헤더 — PlaygroundHeader 구조/스타일 미러.
//   nav 행(뒤로) + 제목 행(24px 제목 좌 / 우측 액션 슬롯). cluster(PlaygroundDetail)의 PlaygroundHeader 와 동일 룩.
export default function DeployDetailHeader({
  title,
  onBack,
  backLabel = '배포 목록',
  right = null,
}) {
  return (
    <div className={cx('header-cont')}>
      <div className={cx('navigate-header-cont')}>
        <button type='button' className={cx('back-btn')} onClick={onBack}>
          <span>← {backLabel}</span>
        </button>
      </div>
      <div className={cx('header-content-cont')}>
        <h2 className={cx('header-title')}>{title}</h2>
        {right && <div className={cx('header-content-right')}>{right}</div>}
      </div>
    </div>
  );
}
