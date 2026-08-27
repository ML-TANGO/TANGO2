// i18n
import { useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { moveRovingFocus } from '@src/utils/a11y';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './EvalProjectFormModal.module.scss';

const cx = classNames.bind(style);

// 평가 유형 3종 — 축은 **누가 채점하나**다. 유형이 이후 실행 화면(무엇을 묻는지)과
// 점수의 척도(0~1 정답률 / 1~10 심판 점수 / 1~5 별점)를 통째로 결정하므로, 라디오 한 줄이
// 아니라 "무엇으로 채점하는지"를 한두 줄로 말하는 카드로 세운다. 잘못 고르면 프로젝트
// 유형은 생성 후 불변이라 되돌릴 방법이 삭제뿐이다.
const TYPE_OPTIONS = [
  {
    value: 'reference',
    label: 'evaluation.project.type.reference',
    desc: 'evaluation.project.typeDesc.reference',
  },
  {
    value: 'judge',
    label: 'evaluation.project.type.judge',
    desc: 'evaluation.project.typeDesc.judge',
  },
  {
    value: 'expert',
    label: 'evaluation.project.type.expert',
    desc: 'evaluation.project.typeDesc.expert',
  },
];

const TYPE_VALUES = TYPE_OPTIONS.map((option) => option.value);

// 새 평가 프로젝트 생성 모달(프레젠테이셔널) — 학습/배포 모달과 동일한 프레임/필드 규격.
//   NewStyleModalFrame(664px·resize·minimize) + InputBoxWithLabel + 디자인시스템 컴포넌트.
//   필드: 이름(InputText) → 평가유형(카드 3종). **모델·데이터셋은 여기서 고르지 않는다** —
//   런을 실행하는 자리(실행 모달)에서 고른다. 한 프로젝트가 여러 모델·데이터셋의 런을
//   담을 수 있어야 비교가 성립하기 때문이다.
//   상태·검증·submit 은 컨테이너 소유(BE 계약: name/eval_type/workspace_id).
function EvalProjectFormModal({
  type,
  data,
  validate,
  name,
  setName,
  evalType,
  setEvalType,
  onSubmit,
}) {
  const { t } = useTranslation();
  const { submit, cancel } = data;
  const groupRef = useRef(null);

  // WAI-ARIA radiogroup — 카드형 옵션이라 디자인시스템 Radio(라벨 텍스트만 렌더)를 쓸 수
  // 없다. 방향키·Home/End 조작은 공용 유틸이 소유한다(@src/utils/a11y).
  const moveType = moveRovingFocus(
    groupRef,
    TYPE_VALUES,
    evalType,
    setEvalType,
  );

  const newSubmit = {
    text: submit.text,
    func: async () => await onSubmit(),
  };

  const title = t('evaluation.project.createTitle');

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={title}
      headerTitle={title}
      submitBtnTestId='create-eval-project-btn'
      customStyle={{ width: '664px' }}
    >
      <div className={cx('form')}>
        {/* ** 이름 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.project.name')}
            labelSize='large'
            disableErrorMsg
          >
            <InputText
              size='medium'
              placeholder={t('evaluation.project.namePlaceholder')}
              name='name'
              value={name}
              onChange={(e) => setName(e.target.value)}
              onClear={() => setName('')}
              options={{ maxLength: 100 }}
              autoFocus
              disableLeftIcon
              testId='eval-project-name-input'
              customStyle={{ fontSize: '14px', fontFamily: 'SpoqaM' }}
            />
          </InputBoxWithLabel>
        </div>

        {/* ** 평가 유형 ** */}
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('evaluation.project.selectType')}
            labelSize='large'
            disableErrorMsg
          >
            <div
              ref={groupRef}
              className={cx('type-cards')}
              role='radiogroup'
              aria-label={t('evaluation.project.selectType')}
              onKeyDown={moveType}
            >
              {TYPE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type='button'
                  role='radio'
                  aria-checked={evalType === option.value}
                  data-value={option.value}
                  tabIndex={evalType === option.value ? 0 : -1}
                  className={cx('type-card', evalType === option.value && 'on')}
                  onClick={() => setEvalType(option.value)}
                >
                  <span className={cx('type-mark')} aria-hidden='true' />
                  <span className={cx('type-body')}>
                    <span className={cx('type-name')}>{t(option.label)}</span>
                    <span className={cx('type-desc')}>{t(option.desc)}</span>
                  </span>
                </button>
              ))}
            </div>
          </InputBoxWithLabel>
        </div>

        {/* 모델·데이터셋은 실행 시점 선택이라 이 폼에 없다(위 주석 참조). */}
      </div>
    </NewStyleModalFrame>
  );
}

export default EvalProjectFormModal;
