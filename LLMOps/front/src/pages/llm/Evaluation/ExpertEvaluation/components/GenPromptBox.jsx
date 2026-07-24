import classNames from 'classnames/bind';
import style from './ExpertReview.module.scss';

const cx = classNames.bind(style);

// 생성 시스템 프롬프트 고정 박스(P3) — 채점 대상 출력을 "생성"할 때 실제 사용된 시스템 프롬프트.
// 사람에게 주는 채점 기준(ExpertPromptBox='평가 지침')과 구분된다. 러너 런의 _gen_system_prompt
// 또는 바인드 배포의 prompt.system_message 에서 온다(표시=실사용 일치). 값 없으면 생략(graceful).
const GenPromptBox = ({ prompt, t }) => {
  if (!prompt) return null;
  return (
    <div className={cx('gen-prompt-box')}>
      <div className={cx('gen-prompt-label')}>
        {t('evaluation.expert.genPromptTitle')}
      </div>
      <p className={cx('gen-prompt-text')}>{prompt}</p>
    </div>
  );
};

export default GenPromptBox;
