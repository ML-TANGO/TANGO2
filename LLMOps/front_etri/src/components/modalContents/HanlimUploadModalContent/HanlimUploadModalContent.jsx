// Templates
import ModalTemplate from '@src/components/templates/ModalTemplate';

// Organisms
import ModalHeader from '@src/components/organisms/modal/ModalHeader';
import ModalFooter from '@src/components/organisms/modal/ModalFooter';

// Components
import File from '@src/components/molecules/File';

// i18n
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './HanlimUploadModalContent.module.scss';
const cx = classNames.bind(style);

function HanlimUploadModalContent({
  title,
  files,
  filesError,
  onSubmit,
  modalData,
  onRemoveFiles,
  isValidate,
  loading,
  message,
  progressRef,
  fileInputHandler,
}) {
  const { t } = useTranslation();
  const { submit, cancel } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      onSubmit(submit.func);
    },
  };

  return (
    <ModalTemplate
      headerRender={<ModalHeader title={title} />}
      footerRender={
        <ModalFooter
          submit={newSubmit}
          cancel={cancel}
          isValidate={isValidate}
          loading={loading}
        />
      }
      customStyle={{
        component: {},
      }}
    >
      <div className={cx('wrapper')}>
        {/* <h2 className={cx('title')}>{t('file.label')}</h2> */}
        <div className={cx('noti')}>{t('dbUpload.message')}</div>
        <File
          name='files'
          onChange={fileInputHandler}
          value={files}
          error={filesError}
          btnText={t('fileUpload.label')}
          onRemove={onRemoveFiles}
          progressRef={progressRef}
          flexStyle='row'
          single={true}
        />
        <div className={cx('row')}>{message}</div>
      </div>
    </ModalTemplate>
  );
}

export default HanlimUploadModalContent;
