import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 고정(sticky) 진행 헤더 — 채점 N/total · 현재 i/total · 이전/다음 · 완료 배지 · 새 평가.
// 진행/평균은 submitExpertRating 응답(progress)에서, i/total 은 로컬 네비게이션 인덱스에서.
const ExpertProgressHeader = ({
  rated,
  total,
  current,
  count,
  avgScore,
  completed,
  onPrev,
  onNext,
  onReset,
  t,
}) => {
  const position = count > 0 ? current + 1 : 0;
  const avg = Number(avgScore) || 0;

  return (
    <div className={cx('ph')}>
      <span className={cx('ph-progress')}>
        {t('evaluation.expert.progress', {
          rated: rated ?? 0,
          total: total ?? count,
        })}
      </span>
      {(rated ?? 0) > 0 && avg > 0 && (
        <span className={cx('ph-avg')}>
          {t('evaluation.expert.avgScore')}: <strong>{avg.toFixed(2)}/5</strong>
        </span>
      )}
      {completed && (
        <span className={cx('ph-done')}>
          {t('evaluation.expert.completed')}
        </span>
      )}
      <div className={cx('ph-spacer')} />
      <span className={cx('ph-position')}>
        {t('evaluation.expert.current', { current: position, total: count })}
      </span>
      <button
        type='button'
        className={cx('ph-nav')}
        onClick={onPrev}
        disabled={current <= 0}
      >
        ‹ {t('evaluation.expert.prev')}
      </button>
      <button
        type='button'
        className={cx('ph-nav')}
        onClick={onNext}
        disabled={current >= count - 1}
      >
        {t('evaluation.expert.next')} ›
      </button>
      <button type='button' className={cx('ph-reset')} onClick={onReset}>
        {t('evaluation.expert.newSession')}
      </button>
    </div>
  );
};

export default ExpertProgressHeader;
