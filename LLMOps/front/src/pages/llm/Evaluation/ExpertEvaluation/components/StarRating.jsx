import { useRef } from 'react';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

const STARS = [1, 2, 3, 4, 5];

// 1~5 별점 입력 — O/X 대체(D2). 접근성: role="radiogroup"/radio + roving tabindex +
// 방향키(←→↑↓/Home/End) 로 점수 이동. 값은 상위 ratings state 에만(transient·서버 영속은 rate()).
const StarRating = ({ value = 0, onChange, disabled = false, t }) => {
  const groupRef = useRef(null);
  const current = Number(value) || 0;

  const focusStar = (score) => {
    const btn = groupRef.current?.querySelector(`[data-score="${score}"]`);
    if (btn) btn.focus();
  };

  const handleKeyDown = (e) => {
    if (disabled) return;
    let next = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp')
      next = Math.min(5, current + 1);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown')
      next = Math.max(1, (current || 1) - 1);
    else if (e.key === 'Home') next = 1;
    else if (e.key === 'End') next = 5;
    if (next == null) return;
    e.preventDefault();
    onChange?.(next);
    focusStar(next);
  };

  return (
    <div
      ref={groupRef}
      className={cx('star-group')}
      role='radiogroup'
      aria-label={t('evaluation.expert.ratingGroupLabel')}
      onKeyDown={handleKeyDown}
    >
      {STARS.map((score) => {
        const filled = score <= current;
        const isSelected = score === current;
        // roving tabindex — 선택된 별(미선택이면 첫 별)만 tab 진입점.
        const isTabStop = isSelected || (current === 0 && score === 1);
        return (
          <button
            key={score}
            type='button'
            data-score={score}
            className={cx('star', filled && 'star--filled')}
            role='radio'
            aria-checked={isSelected}
            aria-label={t('evaluation.expert.starLabel', { score })}
            tabIndex={isTabStop ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange?.(score)}
          >
            {filled ? '★' : '☆'}
          </button>
        );
      })}
      {current > 0 && <span className={cx('star-value')}>{current}/5</span>}
    </div>
  );
};

export default StarRating;
