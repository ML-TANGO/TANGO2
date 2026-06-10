// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputText, InputNumber, Selectbox } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './SubmitInputForm.module.scss';
const cx = classNames.bind(style);

/**
 * DNA+DRONE CHALLENGE 모달 테스트 탭에서 사용되는 필수입력 폼 컴포넌트
 * @param {{
 *    runFile: object,
 *    runFileOptions: Array,
 *    runCommand: string,
 *    answerSheet: object,
 *    answerSheetOptions; Array,
 *    createAnswerSheetFile: object,
 *    createAnswerSheetFileOptions: Array,
 *    runCommand: string,
 *    inferenceTime: number,
 *    packageInstaller: object,
 *    packageInstallerOptions: Array,
 *    selectInputHandler: Function,
 *    textInputHandler: Function,
 * }} props
 * @returns
 */

function SubmitInputForm({
  runFile,
  runFileOptions,
  runCommand,
  answerSheet,
  answerSheetOptions,
  createAnswerSheetFile,
  createAnswerSheetFileOptions,
  answerSheetRunCommand,
  inferenceTime,
  packageInstaller,
  packageInstallerOptions,
  selectInputHandler,
  textInputHandler,
}) {
  const { t } = useTranslation();
  return (
    <>
      <h3 className={cx('input-group-title')}>1. 학습 코드 관련</h3>
      <InputBoxWithLabel labelText='학습 코드 (.py)' labelSize='large'>
        <Selectbox
          size='large'
          list={runFileOptions}
          placeholder={
            runFileOptions.length === 0
              ? '선택 가능한 학습 코드가 없습니다.'
              : '-'
          }
          selectedItem={runFile}
          onChange={(value) => {
            selectInputHandler('runFile', value);
          }}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='학습 실행 Command (parser only)'
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='large'
      >
        <InputText
          size='large'
          value={runCommand}
          name='runCommand'
          onChange={(e) => textInputHandler(e)}
          placeholder=''
        />
      </InputBoxWithLabel>
      <h3 className={cx('input-group-title')}>2. 답안지 관련</h3>
      <InputBoxWithLabel labelText='답안지 (.csv)' labelSize='large'>
        <Selectbox
          size='large'
          list={answerSheetOptions}
          placeholder={
            answerSheetOptions.length === 0
              ? '선택 가능한 답안지가 없습니다.'
              : '-'
          }
          selectedItem={answerSheet}
          onChange={(value) => {
            selectInputHandler('answerSheet', value);
          }}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel labelText='답안지 생성 코드 (.py)' labelSize='large'>
        <Selectbox
          size='large'
          list={createAnswerSheetFileOptions}
          placeholder={
            createAnswerSheetFileOptions.length === 0
              ? '선택 가능한 답안지 생성 코드가 없습니다.'
              : '-'
          }
          selectedItem={createAnswerSheetFile}
          onChange={(value) => {
            selectInputHandler('createAnswerSheetFile', value);
          }}
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText='코드 실행 Command (parser only)'
        labelSize='large'
      >
        <InputText
          size='large'
          value={answerSheetRunCommand}
          name='answerSheetRunCommand'
          onChange={(e) => textInputHandler(e)}
          placeholder=''
        />
      </InputBoxWithLabel>
      <h3 className={cx('input-group-title')}>3. 추론 시간 관련</h3>
      <InputBoxWithLabel labelText='추론 시간 (단위: ms)' labelSize='large'>
        <InputNumber
          size='large'
          value={inferenceTime}
          name='inferenceTime'
          onChange={(e) => textInputHandler(e, 'number')}
          min={0}
        />
      </InputBoxWithLabel>
      <h3 className={cx('input-group-title')}>4. 도커 이미지 관련</h3>
      <InputBoxWithLabel
        labelText='패키지 설치 스크립트 파일 (.sh)'
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='large'
      >
        <Selectbox
          size='large'
          list={packageInstallerOptions}
          placeholder={
            packageInstallerOptions.length === 0
              ? '선택 가능한 패키지 설치 스크립트 파일이 없습니다.'
              : '-'
          }
          selectedItem={packageInstaller}
          onChange={(value) => {
            selectInputHandler('packageInstaller', value);
          }}
        />
      </InputBoxWithLabel>
    </>
  );
}

export default SubmitInputForm;
