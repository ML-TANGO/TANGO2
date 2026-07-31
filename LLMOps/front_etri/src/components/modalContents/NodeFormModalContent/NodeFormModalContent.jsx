// i18n
import { useTranslation } from 'react-i18next';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// Atoms
import Loading from '@src/components/atoms/loading/Loading';

// CSS Module
import classNames from 'classnames/bind';
import style from './NodeFormModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * 노드 생성 및 수정 모달의 컨텐츠 컴포넌트
 * @param {Object} props - 노드 모달 폼 데이터
 * @param {'ADD_NODE' | 'EDIT_NODE'} props.type - 모달 타입
 * @param {{
 *    cancel: {
 *      func: () => {} | undefined,
 *      text: string | undefined
 *    },
 *    submit: {
 *      func: () => {} | undefined,
 *      text: string | undefined,
 *    },
 *    nodeId: number | undefined,
 * }} props.modalData - 모달 Footer의 cancel, submit 버튼 관련 값(버튼에 보여줄 텍스트, 클릭 이벤트) 및 node id 값
 * @param {() => JSX.Element | undefined} props.renderIpAddressInputForm - IP 인풋 컴포넌트 렌더 함수
 * @param {() => JSX.Element | undefined} props.renderServerModeInput - 서버 모드 설정 인풋 컴포넌트 렌더 함수
 * @param {() => JSX.Element | undefined} props.renderServerSettingInput - 서버 리소스 할당 컴포넌트 렌더 함수
 * @param {boolean} props.loading - 입력한 ip 값으로 서버 정보 조회 시 보여줄 로딩 컴포넌트의 제공 여부 값 true -> 로딩 활성화, false -> 로딩 비활성화
 * @param {boolean} props.isGetServerInfo - 서버 정보의 존재 여부
 * @param {boolean} props.isValidate - 활성화된 커스텀 훅의 인풋 값이 유효하면 true 하나라도 유효하지 않으면 false
 * @param {Function} props.onSubmit - Submit 버튼 클릭 이벤트
 * @component
 * @returns {JSX.Element}
 */
function NodeFormModalContent(props) {
  const {
    type,
    modalData,
    renderIpAddressInputForm,
    renderServerModeInput,
    renderServerSettingInput,
    loading,
    isGetServerInfo,
    isValidate,
    onSubmit,
  } = props;

  // 다국어 지원 hooks
  const { t } = useTranslation();

  // 모달 제목
  const title =
    type === 'ADD_NODE'
      ? t('addNodeForm.title.label')
      : t('editNodeForm.title.label');

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
        {/* IP Address 입력 컴포넌트 */}
        {renderIpAddressInputForm()}
        {/* 로딩 */}
        {loading && <Loading />}
        {/* 설정 정보 렌더링 */}
        {!loading && isGetServerInfo && (
          // loading이 false이며 서버 정보가 존재할 때
          // 서버 모드, 리소스 관련 인풋 컴포넌트 렌더링
          <>
            {/* 서버 모드 인풋 컴포넌트 */}
            {renderServerModeInput && renderServerModeInput()}
            {/* 리소스 할당 관련 인풋 컴포넌트 */}
            {renderServerSettingInput && renderServerSettingInput()}
          </>
        )}
      </div>
    </ModalTemplate>
  );
}

export default NodeFormModalContent;
