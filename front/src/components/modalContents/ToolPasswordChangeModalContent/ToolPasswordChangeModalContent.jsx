// i18n
import { useTranslation } from 'react-i18next';

// Components
import ModalFrame from '@src/components/Modal/ModalFrame';
import { InputText, InputPassword } from '@jonathan/ui-react';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Type
import { TRAINING_TOOL_TYPE } from '@src/types';

// CSS module
import classNames from 'classnames/bind';
import style from './ToolPasswordChangeModalContent.module.scss';
const cx = classNames.bind(style);

const ToolPasswordChangeModalContent = ({
  type,
  modalData,
  validate,
  userId,
  password,
  passwordConfirm,
  userIdError,
  passwordError,
  passwordConfirmError,
  textInputHandler,
  onSubmit,
}) => {
  const { t } = useTranslation();
  const { submit, cancel, toolType, toolName, isReset } = modalData;
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
      isClose={true}
      validate={validate}
    >
      <div className={cx('title')}>
        {isReset ? (
          <span>{t('changePasswordForm.title.label')}</span>
        ) : (
          <span>{t('createPasswordForm.title.label')}</span>
        )}
        <span className={cx('divide')}>-</span>
        <img
          className={cx('tool-icon')}
          src={`/images/icon/ic-${TRAINING_TOOL_TYPE[toolType]?.type}.svg`}
          alt={`${TRAINING_TOOL_TYPE[toolType]?.type} icon`}
        />
        <span className={cx('tool-label')}>
          {toolName ? toolName : TRAINING_TOOL_TYPE[toolType]?.label}
        </span>
      </div>
      <div className={cx('form')}>
        <div className={cx('notice')}>
          {isReset
            ? `${t('trainingTool.resetPassword.message')}`
            : `${t('trainingTool.changePassword.message', {
                tool: TRAINING_TOOL_TYPE[toolType]?.label,
              })}`}
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('userID.label')}
            labelSize='large'
            optionalText={
              isReset && t('trainingTool.resetPassword.changeId.message')
            }
            errorMsg={t(userIdError)}
          >
            <InputText
              size='large'
              tabIndex='1'
              name='id'
              placeholder='admin'
              value={isReset ? userId : 'admin'}
              isReadOnly={!isReset}
              onChange={textInputHandler}
              autoFocus={isReset}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={isReset ? t('newPassword.label') : t('password.label')}
            labelSize='large'
            errorMsg={t(passwordError)}
          >
            <InputPassword
              size='large'
              tabIndex='2'
              placeholder={t('newPassword.placeholder')}
              name='password'
              value={password}
              onChange={textInputHandler}
              status={passwordError ? 'error' : 'default'}
              autoFocus={!isReset}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={
              isReset
                ? t('newPasswordConfirm.label')
                : t('passwordConfirm.label')
            }
            labelSize='large'
            errorMsg={t(passwordConfirmError)}
          >
            <InputPassword
              size='large'
              tabIndex='3'
              placeholder={t('newPasswordConfirm.placeholder')}
              name='passwordConfirm'
              value={passwordConfirm}
              onChange={textInputHandler}
              status={passwordConfirmError ? 'error' : 'default'}
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </ModalFrame>
  );
};

export default ToolPasswordChangeModalContent;
