// i18n
import { useCallback, useMemo } from 'react';
import { withTranslation } from 'react-i18next';

import { InputPassword, InputText, Selectbox } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// Components
import NewStyleModalFrame from '../NewStyleModalFrame';

import { isMailValidate } from '@src/utils';

// CSS module
import classNames from 'classnames/bind';
import style from './UserFormModal.module.scss';

const cx = classNames.bind(style);

const UserFormModal = ({
  validate,
  data,
  type,
  name,
  nameError,
  nickname,
  email,
  usergroup,
  userGroupOptions,
  userGroup,
  position,
  passwordError,
  confirmError,
  readOnlyTxt,
  textInputHandler,
  searchSelectHandler,
  onSubmit,
  t,
  footerMessage,
}) => {
  const { submit, cancel, data: userData } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const isValidateMail = useMemo(() => {
    if (email === null) return false;
    return !isMailValidate(email);
  }, [email]);

  const calIsValidateLength = useCallback((inputType) => {
    if (inputType === null) return false;
    return inputType.length === 0;
  }, []);

  const title =
    type === 'CREATE_USER'
      ? t('addUserForm.title.label')
      : `${t('editUserForm.title.label')} - ${name}`;

  const calFooterMessage = () => {
    if (nameError) return t(nameError);
    if (passwordError) return t(passwordError);
    if (confirmError) return t(confirmError);
    if (isValidateMail) return t('email.notMatch.message');
    if (email === '') return t('email.empty.message');
    if (calIsValidateLength(nickname)) return t('nickname.placeholder');
    if (calIsValidateLength(usergroup)) return t('affiliation.placeholder');
    if (calIsValidateLength(position)) return t('position.placeholder');
    return footerMessage;
  };

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={title}
      footerMessage={calFooterMessage()}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('userID.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='name'
            value={name}
            placeholder={t('userID.placeholder')}
            onChange={textInputHandler}
            status={nameError ? 'error' : 'default'}
            isReadOnly={readOnlyTxt === 'edit'}
            disableLeftIcon
            options={{ maxLength: 32 }}
            autoFocus
            tabIndex='1'
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('userGroup.label')}
          labelSize='large'
          disableErrorMsg
        >
          <Selectbox
            type='search'
            size='medium'
            placeholder={t('userGroupSelect.placeholder')}
            list={userGroupOptions}
            selectedItem={userGroup}
            onChange={(selectItem) => {
              searchSelectHandler(selectItem, 'userGroup');
            }}
            customStyle={{
              fontStyle: {
                selectbox: {
                  color: '#121619',
                  textShadow: 'None',
                },
              },
            }}
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row', 'flex-cont')}>
        <InputBoxWithLabel
          labelText={t('password.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputPassword
            size='medium'
            tabIndex='2'
            placeholder={t('userPassword.placeholder')}
            name='password'
            onChange={textInputHandler}
            status={passwordError ? 'error' : 'default'}
            customStyle={{ width: '274px' }}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('passwordConfirm.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputPassword
            size='medium'
            tabIndex='3'
            placeholder={t('userPasswordConfirm.placeholder')}
            name='confirm'
            onChange={textInputHandler}
            status={confirmError ? 'error' : 'default'}
            customStyle={{ width: '274px' }}
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('email')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='email'
            value={email}
            placeholder={t('email.placeholder')}
            onChange={textInputHandler}
            status={isValidateMail ? 'error' : 'default'}
            options={{ maxLength: 33 }}
            disableLeftIcon
            tabIndex='4'
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('name.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='nickname'
            value={nickname}
            placeholder={t('nickname.placeholder')}
            onChange={textInputHandler}
            status={calIsValidateLength(nickname) ? 'error' : 'default'}
            options={{ maxLength: 60 }}
            disableLeftIcon
            tabIndex='4'
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row', 'flex-cont')}>
        <InputBoxWithLabel
          labelText={t('affiliation')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='usergroup'
            value={usergroup}
            placeholder={t('affiliation.placeholder')}
            onChange={textInputHandler}
            status={calIsValidateLength(usergroup) ? 'error' : 'default'}
            options={{ maxLength: 32 }}
            disableLeftIcon
            tabIndex='5'
            customStyle={{ width: '274px' }}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('position.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='position'
            value={position}
            placeholder={t('position.placeholder')}
            onChange={textInputHandler}
            status={calIsValidateLength(position) ? 'error' : 'default'}
            options={{ maxLength: 32 }}
            disableLeftIcon
            tabIndex='6'
            customStyle={{ width: '274px' }}
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default withTranslation()(UserFormModal);
