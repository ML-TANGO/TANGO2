import React, { useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputPassword, InputText } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal, openModal } from '@src/store/modules/modal';
import useInputs from '@src/hooks/useInputs';

import { DeleteButton, ModifyButton } from '../AddWebcrowler/AddWebcrowler';
import NameInput from '../DataCollectModal/NameInput/NameInput';
import useNameInput from '../DataCollectModal/NameInput/useNameInput';
import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './AddRemoteServerModal.module.scss';

const cx = classNames.bind(style);

export const calIsErrorLength = (key) => {
  // ** 초기 값 undefined**
  if (!key) return true;
  if (key.length === 0) return false;
  return true;
};

export const calIsValidate = (key) => {
  if (!key) return false;
  if (key.length === 0) return false;
  return true;
};

export const calIsValidateBtn = (
  isValidateName,
  isValidateId,
  isValidatePassword,
  isValidateIp,
  isValidatePath,
) => {
  if (
    isValidateName &&
    isValidateId &&
    isValidatePassword &&
    isValidateIp &&
    isValidatePath
  )
    return true;
  return false;
};

const calFooterMessage = (name, isValidateName, id, password, ip, path, t) => {
  if (!name) return '원격 서버 이름을 입력해 주세요';
  if (!isValidateName) return t('newNameRule.message');
  if (!id) return '접근 계정 ID를 입력해 주세요';
  if (!password) return '접근 계정 Password를 입력해 주세요';
  if (!ip) return '원격 서버 IP를 입력해 주세요';
  if (ip.length === 0) return '원격 서버 IP를 입력해 주세요';
  if (!path) return '수집 데이터 경로를 입력해 주세요';
  if (path.length === 0) return '수집 데이터 경로를 입력해 주세요';
  return '';
};

// ** 삭제 버튼 핸들러 **
export const handleRemoteServerDeleteButton = (
  name,
  ip,
  setCollectMethodList,
) => {
  setCollectMethodList((prev) => {
    const shallowList = prev['remote_server'].slice();
    const findIndex = shallowList.findIndex(
      ({ first, second }) => first === name && second === ip,
    );
    shallowList.splice(findIndex, 1);
    return {
      ...prev,
      remote_server: shallowList,
    };
  });
};

export default function AddRemoteServerModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const {
    editName,
    editId,
    editPassword,
    editIp,
    editPath,
    setCollectMethodList,
  } = data;

  // ** [수집 이름] **
  const labelText = '원격 서버 이름';
  const placeholder = '원격 서버 이름을 입력하세요.';
  const {
    name,
    isValidateName,
    isError: isNameError,
    handleName,
  } = useNameInput();

  const {
    inputs,
    handleInputs,
    dispatch: inputDispatch,
  } = useInputs({
    id: editId,
    password: editPassword,
    ip: editIp,
    path: editPath,
  });
  const { id, password, ip, path } = inputs;

  // ** [Error : Input error status, validate : isSubmit Btn status] **
  const isErrorId = !calIsErrorLength(id);
  const isValidateId = calIsValidate(id);

  const isErrorPassword = !calIsErrorLength(password);
  const isValidatePassword = calIsValidate(password);

  // ** [IP] **
  const isErrorIp = !calIsErrorLength(ip);
  const isValidateIp = calIsValidate(ip);

  // ** [Path] **
  const isErrorPath = !calIsErrorLength(path);
  const isValidatePath = calIsValidate(path);

  // ** [Footer Message] **
  const footerMessage = calFooterMessage(
    name,
    isValidateName,
    id,
    password,
    ip,
    path,
    t,
  );
  // ** [버튼 유효성 검사] **
  const isValidate = calIsValidateBtn(
    isValidateName,
    isValidateId,
    isValidatePassword,
    isValidateIp,
    isValidatePath,
  );

  // ** 수정 버튼 핸들러 **
  const handleModifyButton = () => {
    dispatch(
      openModal({
        modalType: 'ADD_REMOTE_SERVER',
        modalData: {
          editName: name,
          editId: id,
          editPassword: password,
          editIp: ip,
          editPath: path,
          setCollectMethodList,
        },
      }),
    );
  };

  const submit = {
    text: editName ? t('update.label') : t('add.label'),
    func: () => {
      setCollectMethodList((prev) => {
        const shallowList = prev['remote_server'].slice();
        if (!editId) {
          shallowList.push({
            name,
            ip,
            user: id,
            passwd: password,
            path,
            first: name,
            second: ip,
            third: <ModifyButton handleModifyButton={handleModifyButton} />,
            fourth: (
              <DeleteButton
                handleDeleteButton={() =>
                  handleRemoteServerDeleteButton(name, ip, setCollectMethodList)
                }
              />
            ),
          });
        } else {
          const findValueIdx = shallowList.findIndex(
            ({ first, second }) => first === editName && second === editIp,
          );
          shallowList[findValueIdx].first = name;
          shallowList[findValueIdx].name = name;
          shallowList[findValueIdx].second = ip;
          shallowList[findValueIdx].ip = ip;
          shallowList[findValueIdx].user = id;
          shallowList[findValueIdx].passwd = password;
          shallowList[findValueIdx].path = path;
          shallowList[findValueIdx].third = (
            <ModifyButton handleModifyButton={handleModifyButton} />
          );
          shallowList[findValueIdx].fourth = (
            <DeleteButton
              handleDeleteButton={() =>
                handleRemoteServerDeleteButton(name, ip, setCollectMethodList)
              }
            />
          );
        }

        prev['remote_server'] = shallowList;
        return prev;
      });
      dispatch(closeModal(type));
    },
  };

  useEffect(() => {
    if (editName) {
      handleName(editName);
      inputDispatch({
        name: 'id',
        value: editId,
      });
      inputDispatch({
        name: 'password',
        value: editPassword,
      });
      inputDispatch({
        name: 'ip',
        value: editIp,
      });
      inputDispatch({
        name: 'path',
        value: editPath,
      });
    }
  }, [
    editId,
    editIp,
    editName,
    editPassword,
    editPath,
    handleName,
    inputDispatch,
  ]);

  return (
    <NewStyleModalFrame
      title={editName ? '원격 서버 수정' : '원격 서버 추가'}
      type={type}
      submit={submit}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={isValidate}
      footerMessage={footerMessage}
      customStyle={{ width: '568px' }}
    >
      <NameInput
        value={name}
        labelText={labelText}
        placeholder={placeholder}
        isError={isNameError}
        handleName={handleName}
      />
      <div className={cx('row', 'grid')}>
        <InputBoxWithLabel
          labelText={'접근 계정'}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            name='id'
            placeholder={'ID'}
            value={id}
            onChange={handleInputs}
            status={isErrorId ? 'error' : 'default'}
            options={{ maxLength: 200 }}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelSize='large'
          labelStyle={{ display: 'inline-block', marginTop: '16px' }}
          disableErrorMsg
        >
          <InputPassword
            name='password'
            size='large'
            placeholder={'Password'}
            value={password}
            onChange={handleInputs}
            customStyle={{ height: '36px', fontSize: '14px' }}
            status={isErrorPassword ? 'error' : 'default'}
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={'원격 서버 IP'}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            name='ip'
            placeholder={'원격 서버 IP를 입력하세요'}
            value={ip}
            onChange={handleInputs}
            status={isErrorIp ? 'error' : 'default'}
            options={{ maxLength: 200 }}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={'수집 데이터 경로'}
          labelSize='large'
          optionalText='폴더 또는 파일 경로 입력 가능'
          disableErrorMsg
        >
          <InputText
            name='path'
            value={path}
            placeholder={'수집 데이터 경로를 입력하세요'}
            onChange={handleInputs}
            status={isErrorPath ? 'error' : 'default'}
            options={{ maxLength: 200 }}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
}
