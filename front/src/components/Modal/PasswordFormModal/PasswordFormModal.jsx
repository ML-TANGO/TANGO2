// i18n
import { useTranslation } from 'react-i18next';

// Components
import ModalFrame from '../ModalFrame';
import { InputPassword } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './PasswordFormModal.module.scss';
const cx = classNames.bind(style);

const PasswordFormModal = ({
  validate,
  data,
  type,
  passwordError,
  newPasswordError,
  confirmError,
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
      <h2 className={cx('title')}>{t('changePasswordForm.title.label')}</h2>
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('currentPassword.label')}
            labelSize='large'
            errorMsg={t(passwordError)}
          >
            <InputPassword
              size='large'
              tabIndex='1'
              placeholder={t('currentPassword.placeholder')}
              name='password'
              onChange={textInputHandler}
              status={passwordError ? 'error' : 'default'}
              autoFocus={true}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('newPassword.label')}
            labelSize='large'
            errorMsg={t(newPasswordError)}
          >
            <InputPassword
              size='large'
              tabIndex='2'
              placeholder={t('newPassword.placeholder')}
              name='newPassword'
              onChange={textInputHandler}
              status={newPasswordError ? 'error' : 'default'}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('newPasswordConfirm.label')}
            labelSize='large'
            errorMsg={t(confirmError)}
          >
            <InputPassword
              size='large'
              tabIndex='3'
              placeholder={t('newPasswordConfirm.placeholder')}
              name='confirm'
              onChange={textInputHandler}
              status={confirmError ? 'error' : 'default'}
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </ModalFrame>
  );
};

export default PasswordFormModal;
