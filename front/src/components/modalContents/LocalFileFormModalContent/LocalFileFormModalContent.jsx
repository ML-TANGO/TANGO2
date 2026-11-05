// i18n
import { useTranslation } from 'react-i18next';

// Molecules
import UploadFormWithPath from '@src/components/molecules/UploadFormWithPath';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';
// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// CSS Module
import classNames from 'classnames/bind';
import style from './LocalFileFormModalContent.module.scss';

const cx = classNames.bind(style);

/**
 * 데이터셋 로컬 파일/폴더 업로드 모달의 컨텐츠 컴포넌트
 * @param {Object} props - 로컬 파일/폴더 업로드 모달 폼 데이터
 * @param {'UPLOAD_FILE'} props.type - 모달 타입
 * @param {{
 *    cancel: {
 *      func: () => {} | undefined,
 *      text: string | undefined
 *    },
 *    submit: {
 *      func: () => {} | undefined,
 *      text: string | undefined,
 *    },
 *    datasetId: string,
 *    loc: string,
 *    workspaceName: string,
 *    workspaceId: number,
 *    datasetName: string,
 * }} props.modalData - 모달 Footer의 cancel, submit 버튼 관련 값(버튼에 보여줄 텍스트, 클릭 이벤트)
 * @param {() => JSX.Element | undefined} props.renderDataInputForm - 파일/폴더 인풋 컴포넌트 렌더 함수
 * @param {boolean} props.isValidate - 활성화된 커스텀 훅의 인풋 값이 유효하면 true
 * @param {Function} props.onSubmit - Submit 버튼 클릭 이벤트
 * @returns {JSX.Element}
 */
function LocalFileFormModalContent({
  type,
  modalData,
  renderDataInputForm,
  isValidate,
  onSubmit,
}) {
  const { t } = useTranslation();

  // 모달 제목
  const title = t('uploadFileForm.title.label');

  const { submit, cancel, datasetName, loc } = modalData;
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
        <UploadFormWithPath datasetName={datasetName} path={loc}>
          {renderDataInputForm()}
        </UploadFormWithPath>
      </div>
    </ModalTemplate>
  );
}

export default LocalFileFormModalContent;
