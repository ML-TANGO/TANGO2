import { ButtonV2 } from '@jonathan/ui-react';

import GuideBox from '@src/components/molecules/GuideBox';

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
  const avg = Number(avgScore) || 0;
  const distributionText = SCORES.map(
    (score, index) => `${score}: ${counts[index]}`,
  ).join(' · ');

  return (
    <div className={cx('completion')}>
      {/* ⚠️ GuideBox 는 textList 각 항목을 sanitizer 없이 dangerouslySetInnerHTML 로 렌더한다.
          여기 넘기는 값이 안전한 이유는 (1) 정적 i18n 라벨과 (2) 위에서 Number(...) || 0 으로
          강제 캐스팅한 숫자(avg/counts)뿐이기 때문이다. 채점 코멘트·rater 명·BE 문자열 등
          자유 텍스트를 이 textList 에 추가하면 그 즉시 XSS 가 된다 — 추가해야 하면 GuideBox 대신
          plain JSX({value}) 로 렌더하라(ExpertPromptBox 방식). */}
      <GuideBox
        title={t('evaluation.expert.completeTitle')}
        isTitleIcon
        textList={[
          `${t('evaluation.expert.avgScore')}: ${avg.toFixed(2)}/5`,
          `${t('evaluation.expert.distribution')}: ${distributionText}`,
        ]}
      />
      <div className={cx('completion-actions')}>
        <ButtonV2
          type='outline'
          colorType='blue'
          size='s'
          label={t('evaluation.expert.newSession')}
          onClick={onReset}
        />
      </div>
    </div>
  );
};

export default ExpertCompletionBanner;
