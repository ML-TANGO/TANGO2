import { Badge, ButtonV2 } from '@jonathan/ui-react';

import ContentBox from '@src/components/molecules/ContentBox';

import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 완료 상태는 조나단 Badge type으로 매핑한다.
const STATUS_BADGE_TYPE = {
  completed: 'green',
};

// 고정(sticky) 진행 헤더 — 세션 제목 · 채점 N/total · 현재 i/total · 이전/다음 · 완료 배지 · 새 평가.
// 진행/평균은 submitExpertRating 응답(progress)에서, i/total 은 로컬 네비게이션 인덱스에서.
// runName 은 생성 시 입력해 동결된 세션 제목(없으면 줄 자체를 생략 — graceful).
const ExpertProgressHeader = ({
  runName,
  rated,
  total,
  current,
  count,
  avgScore,
  completed,
  onPrev,
  onNext,
  nextBlocked,
  onReset,
  t,
}) => {
  const position = count > 0 ? current + 1 : 0;
  const avg = Number(avgScore) || 0;

  return (
    <ContentBox>
      <div className={cx('ph')}>
        <div className={cx('ph-summary')}>
          {runName && <span className={cx('ph-name')}>{runName}</span>}
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
              size='lg'
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
            size='m'
            label={t('evaluation.expert.prev')}
            onClick={onPrev}
            disabled={current <= 0}
          />
          {/* nextBlocked = 낮은 점수인데 코멘트가 비어 있음 — 사유를 남기기 전에는 다음으로
              넘어가지 못하게 잠근다(왜 잠겼는지는 코멘트 입력 아래 안내문 + title 로 전달). */}
          <ButtonV2
            type='outline'
            colorType='blue'
            size='m'
            label={t('evaluation.expert.next')}
            onClick={onNext}
            disabled={current >= count - 1 || !!nextBlocked}
            title={
              nextBlocked ? t('evaluation.expert.nextBlocked') : undefined
            }
          />
          <ButtonV2
            type='clear'
            colorType='gray'
            size='m'
            label={t('evaluation.expert.newSession')}
            onClick={onReset}
          />
        </div>
      </div>
    </ContentBox>
  );
};

export default ExpertProgressHeader;
