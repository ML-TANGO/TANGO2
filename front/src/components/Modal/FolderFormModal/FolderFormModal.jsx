import { useEffect } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import TextInput from '@src/components/atoms/input/TextInput';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Components
import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './FolderFormModal.module.scss';

const cx = classNames.bind(style);

function FolderFormModal({
  validate,
  data,
  type,
  folderName,
  folderNameError,
  textInputHandler,
  onSubmit,
  datasetName,
  loc,
  footerMessage,
}) {
  const { t } = useTranslation();
  const { submit, cancel } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  useEffect(() => {
    const listener = (e) => {
      if (validate && (e.key === 'Enter' || e.key === 'NumpadEnter')) {
        if (submit.func) {
          onSubmit(submit.func);
        }
      }
    };
    document.addEventListener('keydown', listener);
    return () => {
      document.removeEventListener('keydown', listener);
    };
  }, [validate, onSubmit, submit]);

  const title =
    type === 'CREATE_FOLDER'
      ? t('createFolderForm.title.label')
      : t('editFolderForm.title.label');

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      headerTitle={title}
      title={title}
      type={type}
      isResize={true}
      isMinimize={true}
      footer
      validate={validate}
      footerMessage={footerMessage}
      customStyle={{
        width: '664px',
        maxHeight: '750px',
      }}
    >
      <div className={cx('row')}>
        <div className={cx('label')}>{t('folderName.label')}</div>
        <InputBoxWithLabel
          labelText={`/${datasetName}${loc}`}
          leftLabel
          className={cx('dataset-label')}
          // bgBox
        >
          <TextInput
            label={t('folderName.label')}
            placeholder={t('folderName.placeholder')}
            value={folderName}
            name='folderName'
            onChange={textInputHandler}
            status={
              folderNameError === null
                ? ''
                : folderNameError === ''
                ? 'success'
                : 'error'
            }
            maxLength={50}
            autoFocus={true}
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
}

export default FolderFormModal;
