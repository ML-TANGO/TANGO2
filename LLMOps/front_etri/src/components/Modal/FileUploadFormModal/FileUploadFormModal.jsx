// i18n
import { withTranslation } from 'react-i18next';

// Components
import ModalFrame from '../ModalFrame';
import Radio from '@src/components/atoms/input/Radio';
import UploadFormWithPath from '@src/components/molecules/UploadFormWithPath';
import Folder from '@src/components/molecules/Folder';
import File from '@src/components/molecules/File';

// CSS module
import classNames from 'classnames/bind';
import style from './FileUploadFormModal.module.scss';
const cx = classNames.bind(style);

const FileUploadFormModal = ({
  data,
  fileInputHandler,
  files,
  filesError,
  folderInputHandler,
  folders,
  uploadTypeOptions,
  uploadType,
  radioBtnHandler,
  onRemoveFiles,
  onRemoveFolder,
  onSubmit,
  progressRef,
  validate,
  type,
  t,
}) => {
  const { submit, cancel, datasetName, loc } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };
  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      customStyle={{ width: '650px' }}
    >
      <h2 className={cx('title')}>{t('uploadFileForm.title.label')}</h2>
      <div className={cx('form')}>
        <UploadFormWithPath datasetName={datasetName} path={loc}>
          <div className={cx('row', 'upload-type')}>
            <Radio
              name='uploadType'
              options={uploadTypeOptions}
              value={uploadType}
              onChange={radioBtnHandler}
            />
          </div>
          <div className={cx('row')}>
            {uploadType === 0 ? (
              <File
                name='files'
                onChange={fileInputHandler}
                value={files}
                error={filesError}
                btnText={t('browse.label')}
                onRemove={onRemoveFiles}
                progressRef={progressRef}
              />
            ) : (
              <Folder
                name='files'
                onChange={folderInputHandler}
                value={folders}
                error={filesError}
                btnText={t('browse.label')}
                onRemove={onRemoveFolder}
                progressRef={progressRef}
                directory
              />
            )}
          </div>
        </UploadFormWithPath>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(FileUploadFormModal);
