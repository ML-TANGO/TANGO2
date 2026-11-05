// Components
import { Selectbox, Button } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './TestInputForm.module.scss';
const cx = classNames.bind(style);

/**
 * DNA+DRONE CHALLENGE 모달 테스트 탭에서 사용되는 필수입력 폼 컴포넌트
 * @param {
 *   { answerSheet: object,
 *     answerSheetOptions: Array,
 *     inputHandler: Function,
 *     onTest: Function,
 *     testTarget: string,
 *     scroe: number }
 * } props
 */
function TestInputForm({
  answerSheet,
  answerSheetOptions,
  inputHandler,
  onTest,
  testTarget,
  score,
}) {
  return (
    <>
      <div className={cx('inline')}>
        <InputBoxWithLabel labelText='답안지' labelSize='large' disableErrorMsg>
          <Selectbox
            size='large'
            list={answerSheetOptions}
            placeholder={
              answerSheetOptions.length === 0
                ? '선택 가능한 답안지가 없습니다.'
                : '-'
            }
            selectedItem={answerSheet}
            onChange={(e) => {
              inputHandler(e);
            }}
          />
        </InputBoxWithLabel>
        <Button
          size='large'
          type='primary'
          disabled={!answerSheet}
          onClick={() => onTest()}
        >
          테스트 실행
        </Button>
      </div>
      <InputBoxWithLabel labelText='테스트 결과' labelSize='large'>
        <div className={cx('test-result-box')}>
          <div>
            <label className={cx('test-target-label')}>테스트 대상 : </label>
            <span>{testTarget || '-'}</span>
          </div>
          <div className={cx('score-box')}>
            <label className={cx('score-label')}>AP : </label>
            <span className={cx('score')}>
              {score !== undefined ? score : '-'}
            </span>
          </div>
        </div>
      </InputBoxWithLabel>
    </>
  );
}

export default TestInputForm;
