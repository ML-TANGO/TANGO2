import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

const SCORES = [1, 2, 3, 4, 5];

// 완료 배너 — 평균점수(/5) + 1~5 분포 막대 + 새 평가(초기화).
// distribution 은 객체({1:n..5:n}) 우선, 배열([n,n,n,n,n]) 폴백 모두 허용.
const ExpertCompletionBanner = ({ avgScore, distribution, onReset, t }) => {
  const getCount = (score, idx) => {
    if (!distribution) return 0;
    if (Array.isArray(distribution)) return Number(distribution[idx]) || 0;
    return Number(distribution[score] ?? distribution[String(score)]) || 0;
  };
  const counts = SCORES.map((s, i) => getCount(s, i));
  const max = Math.max(1, ...counts);
  const avg = Number(avgScore) || 0;

  return (
    <div className={cx('cb')}>
      <div className={cx('cb-head')}>
        <span className={cx('cb-title')}>
          {t('evaluation.expert.completeTitle')}
        </span>
        <span className={cx('cb-avg')}>
          {t('evaluation.expert.avgScore')} <strong>{avg.toFixed(2)}</strong>/5
        </span>
      </div>

      <div className={cx('cb-dist')}>
        <span className={cx('cb-dist-label')}>
          {t('evaluation.expert.distribution')}
        </span>
        <div className={cx('cb-bars')}>
          {SCORES.map((s, i) => (
            <div key={s} className={cx('cb-bar-row')}>
              <span className={cx('cb-bar-star')}>{s}★</span>
              <div className={cx('cb-bar-track')}>
                <div
                  className={cx('cb-bar-fill')}
                  style={{ width: `${(counts[i] / max) * 100}%` }}
                />
              </div>
              <span className={cx('cb-bar-count')}>{counts[i]}</span>
            </div>
          ))}
        </div>
      </div>

      <button type='button' className={cx('cb-reset')} onClick={onReset}>
        {t('evaluation.expert.newSession')}
      </button>
    </div>
  );
};

export default ExpertCompletionBanner;
