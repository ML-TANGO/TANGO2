// i18n
import { useTranslation } from 'react-i18next';

// Components
import { InputText } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import ModalFrame from '../ModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './FileFormModal.module.scss';
const cx = classNames.bind(style);

const FileFormModal = ({
  validate,
  data,
  type,
  fileName,
  fileNameError,
  textInputHandler,
  onSubmit,
}) => {
  const { t } = useTranslation();
  const { submit, cancel } = data;
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
    >
      <h2 className={cx('title')}>{t('editFileForm.title.label')}</h2>
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('fileName.label')}
            labelSize='large'
            errorMsg={t(fileNameError)}
          >
            <InputText
              size='large'
              placeholder={t('fileName.placeholder')}
              value={fileName}
              name='fileName'
              onChange={textInputHandler}
              status={fileNameError ? 'error' : 'default'}
              options={{ maxLength: 50 }}
              disableLeftIcon
              disableClearBtn
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </ModalFrame>
  );
};

export default FileFormModal;
