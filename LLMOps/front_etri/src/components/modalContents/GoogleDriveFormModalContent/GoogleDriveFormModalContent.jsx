// i18n
import { useTranslation } from 'react-i18next';

// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// Molecules
import UploadFormWithPath from '@src/components/molecules/UploadFormWithPath';

// CSS Module
import classNames from 'classnames/bind';
import style from './GoogleDriveFormModalContent.module.scss';
const cx = classNames.bind(style);

/**
 * 데이터셋 Google Drive 모달의 컨텐츠 컴포넌트
 * @returns
 */
function GoogleDriveFormModalContent({
  type,
  modalData,
  renderDataInputForm,
  isValidate,
  onSubmit,
  loading,
}) {
  const { t } = useTranslation();

  // 모달 제목
  const title = t('googleDrive.title.label');

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
          loading={loading}
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

export default GoogleDriveFormModalContent;
