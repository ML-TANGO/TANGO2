import { useState, useEffect } from 'react';

// Custom Hooks
import useTestInput from './hooks/useTestInput';
import useSubmitInput from './hooks/useSubmitInput';

// Components
import DroneChallengeModalContent from '@src/components/modalContents/DroneChallengeModalContent';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_SUCCESS, STATUS_FAIL } from '@src/network';

function DroneChallengeModal({ type, data: modalData }) {
  // 학습 Id
  const { trainingId } = modalData;
  // 로딩
  const [loading, setLoading] = useState(false);
  // Custom Hooks
  const [setTestState, renderTestInputForm] = useTestInput(trainingId);
  const [submitState, setSubmitState, renderSubmitInputForm] = useSubmitInput();
  const isValidate = submitState.isValid;

  // Events

  /**
   * 업로드 버튼 클릭 이벤트
   * @returns {Promise<boolean>} true를 리턴하면 모달 닫기
   */
  const onSubmit = async (callback) => {
    setLoading(true);
    const {
      runFile,
      runCommand,
      answerSheet,
      createAnswerSheetFile,
      answerSheetRunCommand,
      inferenceTime,
      packageInstaller,
    } = submitState;

    const body = {
      training_id: trainingId,
      training_file_path: runFile.value,
      answer_sheet_file_path: answerSheet.value,
      answer_sheet_create_file_path: createAnswerSheetFile.value,
      answer_sheet_create_command: answerSheetRunCommand,
      inference_time: inferenceTime,
    };

    if (runCommand) {
      body.training_file_command = runCommand;
    }

    if (packageInstaller) {
      body.package_installer_path = packageInstaller.value;
    }

    const response = await callApi({
      url: 'dna/leaderboard',
      method: 'post',
      body,
    });
    const { result, status, message } = response;
    if (status === STATUS_SUCCESS) {
      setLoading(false);
      const count = result.remaining_number;
      toast.info(`제출이 완료되었습니다. 오늘 남은 제출 횟수 : ${count}회`);
      if (callback) callback();
      return true;
    }
    toast.error(message);
    return false;
  };

  // LifeCycle
  useEffect(() => {
    // 노드 정보 조회
    const getOptions = async () => {
      const response = await callApi({
        url: `dna/files?training_id=${trainingId}`,
        method: 'get',
      });

      const { result, message, status } = response;
      if (status === STATUS_SUCCESS) {
        setTestState(result);
        setSubmitState(result);
      } else if (status === STATUS_FAIL) {
        toast.error(message);
      } else {
        toast.error('Fail');
      }
    };
    getOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <DroneChallengeModalContent
      type={type}
      modalData={modalData}
      renderTestInputForm={renderTestInputForm}
      renderSubmitInputForm={renderSubmitInputForm}
      isValidate={isValidate}
      onSubmit={onSubmit}
      loading={loading}
    />
  );
}

export default DroneChallengeModal;
