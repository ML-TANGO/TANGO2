import { Badge, ButtonV2 } from '@jonathan/ui-react';

import ContentBox from '@src/components/molecules/ContentBox';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 완료 상태는 조나단 Badge type으로 매핑한다.
const STATUS_BADGE_TYPE = {
  completed: 'green',
};

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
    <ContentBox>
      <div className={cx('ph')}>
        <div className={cx('ph-summary')}>
          <span className={cx('ph-progress')}>
            {t('evaluation.expert.progress', {
              rated: rated ?? 0,
              total: total ?? count,
            })}
          </span>
          {(rated ?? 0) > 0 && avg > 0 && (
            <span className={cx('ph-avg')}>
              {t('evaluation.expert.avgScore')}:{' '}
              <strong>{avg.toFixed(2)}/5</strong>
            </span>
          )}
          {completed && (
            <Badge
              label={t('evaluation.expert.completed')}
              type={STATUS_BADGE_TYPE.completed}
              size='sm'
            />
          )}
        </div>
        <div className={cx('ph-spacer')} />
        <span className={cx('ph-position')}>
          {t('evaluation.expert.current', { current: position, total: count })}
        </span>
        <div className={cx('ph-actions')}>
          <ButtonV2
            type='outline'
            colorType='blue'
            size='s'
            label={t('evaluation.expert.prev')}
            onClick={onPrev}
            disabled={current <= 0}
          />
          <ButtonV2
            type='outline'
            colorType='blue'
            size='s'
            label={t('evaluation.expert.next')}
            onClick={onNext}
            disabled={current >= count - 1}
          />
          <ButtonV2
            type='clear'
            colorType='gray'
            size='s'
            label={t('evaluation.expert.newSession')}
            onClick={onReset}
          />
        </div>
      </div>
    </ContentBox>
  );
};

export default ExpertProgressHeader;
