import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 고정 프롬프트 박스(D3) — 시나리오 결속 고정 지침(BE 상수, 세션 동결). 사용자 입력 없음.
// graceful(D5): 프롬프트 없으면 생략(일반 데이터셋에서 기본값이 오지 않을 때).
const ExpertPromptBox = ({ prompt, t }) => {
  if (!prompt) return null;
  return (
    <div className={cx('prompt-box')}>
      <div className={cx('prompt-label')}>
        {t('evaluation.expert.promptTitle')}
      </div>
      <p className={cx('prompt-text')}>{prompt}</p>
    </div>
  );
};

export default ExpertPromptBox;
