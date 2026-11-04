import { useState } from 'react';

import TestInputForm from '@src/components/modalContents/DroneChallengeModalContent/TestInputForm';
// Components
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

/**
 * DNA+DRNOE CHALLENGE 모달에서 답안지 입력 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 *
 * @param {'DRNOE_CHALLENGE'} trainingId
 *
 * 리턴 값(배열)의 첫번째 인덱스 값은 입력한 answerSheet 정보를 리턴한다.
 * 두번째 인덱스 값은 해당 answerSheet를 화면에 렌더링하는 함수이다.
 *
 * @component
 * @example
 *
 * const [
 *  setTestState, // answerSheet 옵션 세팅 함수
 *  renderTestInputForm, // answerSheet 인풋 렌더링 함수
 * ] = useTestInput();
 *
 * return (
 *  <>
 *    {renderTestInputForm()}
 *  </>
 * );
 *
 */
const useTestInput = (trainingId) => {
  // Component State
  const [answerSheet, setAnswerSheet] = useState();
  const [answerSheetOptions, setAnswerSheetOptions] = useState([]);
  const [testTarget, setTestTarget] = useState();
  const [score, setScore] = useState();

  // Events
  /**
   * 셀렉트 박스 핸들러
   * @param {{ label: string, value: string }} s 선택된 옵션 값
   */
  const selectInputHandler = (s) => {
    setAnswerSheet(s);
  };

  const onTest = async () => {
    const answerSheetFilePath = answerSheet.value;
    setTestTarget(answerSheetFilePath);
    toast.info(
      '답지 테스트를 진행합니다. 진행에는 1분 미만의 시간이 소요될 수 있습니다.',
    );
    const response = await callApi({
      url: `dna/score?training_id=${trainingId}&answer_sheet_file_path=${answerSheetFilePath}`,
      method: 'get',
    });
    const { result, status, message } = response;
    if (status === STATUS_SUCCESS) {
      setScore(result.score);
      // toast.success('success');
      return true;
    }
    toast.error(message);
    return false;
  };

  const setTestState = (options) => {
    const { answer_sheet_list: answerSheetList } = options;
    setAnswerSheetOptions(
      answerSheetList.map((a) => ({
        label: a,
        value: a,
      })),
    );
  };

  // URL 컴포넌트 렌더링 함수
  const renderTestInput = () => {
    return (
      <TestInputForm
        answerSheet={answerSheet}
        answerSheetOptions={answerSheetOptions}
        inputHandler={selectInputHandler}
        onTest={onTest}
        testTarget={testTarget}
        score={score}
      />
    );
  };

  return [setTestState, renderTestInput];
};

export default useTestInput;
