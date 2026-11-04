// i18n
import { withTranslation } from 'react-i18next';

// Components
import ModalFrame from '../ModalFrame';
import { Textarea } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './WsDescFormModal.module.scss';
const cx = classNames.bind(style);

const WsDescFormModal = ({
  data,
  type,
  validate,
  description,
  descriptionError,
  inputHandler,
  onSubmit,
  t,
}) => {
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
      <h2 className={cx('title')}>{t('editWorkspaceDescForm.title.label')}</h2>
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('workspaceDescription.label')}
            labelSize='large'
            errorMsg={t(descriptionError)}
          >
            <Textarea
              size='large'
              placeholder={t('workspaceDescription.placeholder')}
              value={description}
              name='description'
              onChange={inputHandler}
              status={descriptionError ? 'error' : 'default'}
              isShowMaxLength
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(WsDescFormModal);
