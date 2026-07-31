import { useState, useMemo } from 'react';

// Components
import SubmitInputForm from '@src/components/modalContents/DroneChallengeModalContent/SubmitInputForm';

/**
 * DNA+DRNOE CHALLENGE 모달에서 답안지 제출 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param {'DRNOE_CHALLENGE'} modalData
 * @returns {[
 *  {
 *    runFile: {label: '', value: ''},
 *    runCommand: string,
 *    answerSheet: {label: '', value: ''},
 *    createAnswerSheetFile: {label: '', value: ''},
 *    runCommand: string,
 *    inferenceTime: number,
 *    packageInstaller: {label: '', value: ''},
 *    isValid: boolean,
 *  },
 *  () => JSX.Element
 * ]}
 * 리턴 값(배열)의 첫번째 인덱스 값은 입력한 인풋 정보를 리턴한다.
 * 두번째 인덱스 값은 해당 인풋을 화면에 렌더링하는 함수이다.
 *
 * @component
 * @example
 *
 * const [
 *  submitState, // 인풋 관련 컴포넌트 상태
 *  setSubmitState // 인풋 옵션 세팅 함수
 *  renderSubmitInputForm, // 인풋 렌더링 함수
 * ] = useSubmitInput();
 *
 * return (
 *  <>
 *    {renderSubmitInputForm()}
 *  </>
 * );
 *
 */
const useSubmitInput = () => {
  // Component State
  // 학습 코드 (.py)
  const [runFile, setRunFile] = useState();
  const [runFileOptions, setRunFileOptions] = useState([]);

  // 학습 실행 Command
  const [runCommand, setRunCommand] = useState('');

  // 답안지 (.csv)
  const [answerSheet, setAnswerSheet] = useState();
  const [answerSheetOptions, setAnswerSheetOptions] = useState([]);

  // 답안지 생성 코드 (.py)
  const [createAnswerSheetFile, setCreateAnswerSheetFile] = useState();
  const [createAnswerSheetFileOptions, setCreateAnswerSheetFileOptions] =
    useState([]);

  // 답안지 실행 Command
  const [answerSheetRunCommand, setAnswerSheetRunCommand] = useState('');

  // 추론 시간
  const [inferenceTime, setInferenceTime] = useState(0);

  // 패키지 설치 스크립트 파일 (.sh)
  const [packageInstaller, setPackageInstaller] = useState();
  const [packageInstallerOptions, setPackageInstallerOptions] = useState([]);

  // Events
  /**
   * 셀렉트 박스 핸들러
   * @param { name: string, value: string } s 선택된 옵션 값
   */
  const selectInputHandler = (name, value) => {
    if (name === 'runFile') {
      setRunFile(value);
    } else if (name === 'answerSheet') {
      setAnswerSheet(value);
    } else if (name === 'createAnswerSheetFile') {
      setCreateAnswerSheetFile(value);
    } else if (name === 'packageInstaller') {
      setPackageInstaller(value);
    }
  };

  /**
   * 텍스트 인풋 핸들러
   * @param {Object} e Event 객체
   */
  const textInputHandler = (e, type) => {
    const { name, value } = type === 'number' ? e : e.target;
    if (name === 'runCommand') {
      setRunCommand(value);
    } else if (name === 'answerSheetRunCommand') {
      setAnswerSheetRunCommand(value);
    } else if (name === 'inferenceTime') {
      setInferenceTime(Number(value));
    }
  };

  const setSubmitState = (options) => {
    const {
      run_file_list: runFileList,
      answer_sheet_list: answerSheetList,
      answer_sheet_create_file_list: answerSheetCreateFileList,
      package_installer_list: packageInstallerList,
    } = options;
    setRunFileOptions(
      runFileList.map((v) => ({
        label: v,
        value: v,
      })),
    );
    setAnswerSheetOptions(
      answerSheetList.map((v) => ({
        label: v,
        value: v,
      })),
    );
    setCreateAnswerSheetFileOptions(
      answerSheetCreateFileList.map((v) => ({
        label: v,
        value: v,
      })),
    );
    setPackageInstallerOptions(
      packageInstallerList.map((v) => ({
        label: v,
        value: v,
      })),
    );
  };

  // URL 컴포넌트 렌더링 함수
  const renderSubmitInput = () => {
    return (
      <SubmitInputForm
        runFile={runFile}
        runFileOptions={runFileOptions}
        runCommand={runCommand}
        answerSheet={answerSheet}
        answerSheetOptions={answerSheetOptions}
        createAnswerSheetFile={createAnswerSheetFile}
        createAnswerSheetFileOptions={createAnswerSheetFileOptions}
        answerSheetRunCommand={answerSheetRunCommand}
        inferenceTime={inferenceTime}
        packageInstaller={packageInstaller}
        packageInstallerOptions={packageInstallerOptions}
        selectInputHandler={selectInputHandler}
        textInputHandler={textInputHandler}
      />
    );
  };

  const result = useMemo(
    () => ({
      runFile,
      runCommand,
      answerSheet,
      createAnswerSheetFile,
      answerSheetRunCommand,
      inferenceTime,
      packageInstaller,
      isValid:
        runFile &&
        answerSheet &&
        createAnswerSheetFile &&
        answerSheetRunCommand !== '' &&
        inferenceTime !== 0,
    }),
    [
      runFile,
      runCommand,
      answerSheet,
      createAnswerSheetFile,
      answerSheetRunCommand,
      inferenceTime,
      packageInstaller,
    ],
  );

  return [result, setSubmitState, renderSubmitInput];
};

export default useSubmitInput;
