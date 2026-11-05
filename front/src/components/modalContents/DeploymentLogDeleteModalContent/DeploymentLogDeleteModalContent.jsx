// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// Components
import WorkerListView from '@src/components/modalContents/DeploymentLogDeleteModalContent/WorkerListView';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeploymentLogDeleteModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * 배포 로그 삭제 모달 컨텐츠 컴포넌트
 * @param {Object} props - 배포 로그 삭제 모달 폼 데이터
 * @param {'DEPLOYMENT_LOG_DELETE'} props.type - 모달 타입
 * @param {{
 *    cancel: {
 *      func: () => {} | undefined,
 *      text: string | undefined
 *    },
 *    submit: {
 *      func: () => {} | undefined,
 *      text: string | undefined,
 *    },
 * }} props.modalData - 모달 Footer의 cancel, submit 버튼 관련 값(버튼에 보여줄 텍스트, 클릭 이벤트) 및 deployment id 값
 * @param {string} props.title 모달 타이틀
 * @param {boolean} props.isValidate - 활성화된 커스텀 훅의 인풋 값이 유효하면 true 하나라도 유효하지 않으면 false
 * @param {Function} props.onSubmit - Submit 버튼 클릭 이벤트
 * @param {boolean} props.isConfirmMessage - 삭제 확인 메시지 보여주기 유무
 * @param {Function} props.renderTimeSettingInput - 시간 설정 인풋 렌더링 함수
 * @param {Function} props.renderDeleteConfirmMessage - 삭제 확인 메시지 인풋 렌더링 함수
 * @param {object} props.workerListByDate - 설정시간 이전에 포함되는 워커 리스트
 * @param {string} props.workerListMessage - 워커리스트 에러메시지
 * @returns {JSX.Element}
 */
function DeploymentLogDeleteModalContent({
  type,
  title,
  modalData,
  onSubmit,
  isValidate,
  isConfirmMessage,
  renderTimeSettingInput,
  renderDeleteConfirmMessage,
  workerListByDate,
  workerListMessage,
}) {
  const { submit, cancel } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  return (
    <ModalTemplate
      headerRender={<ModalHeader title={title} />}
      footerRender={
        <ModalFooter
          submit={newSubmit}
          cancel={cancel}
          type={type}
          isValidate={isValidate}
        />
      }
    >
      <div className={cx('modal-content')}>
        <div className={cx('row')}>{renderTimeSettingInput()}</div>
        {workerListByDate && (
          <WorkerListView
            list={workerListByDate}
            errorMessage={workerListMessage}
          />
        )}
        {isConfirmMessage && (
          <div className={cx('row')}>{renderDeleteConfirmMessage()}</div>
        )}
      </div>
    </ModalTemplate>
  );
}

export default DeploymentLogDeleteModalContent;
