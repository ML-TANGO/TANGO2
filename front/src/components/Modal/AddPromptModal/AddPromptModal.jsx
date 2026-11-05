import React, { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText, Textarea } from '@jonathan/ui-react';

import AccessOwnerSelect from '@src/components/molecules/AccessOwnerSelect';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import { getPromptOwner, postPrompts } from '@src/apis/llm/prompt';
import { closeModal } from '@src/store/modules/modal';
import useOwnerList from '@src/hooks/useOwnerList';
import { STATUS_SUCCESS } from '@src/network';

import {
  calNameErrorMsg,
  calNameValidate,
} from '../AddPlayground/AddPlayground';
import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddPromptModal.module.scss';

const cx = classNames.bind(style);

const handleInput = (e, part, setWorkspaceInfo) => {
  setWorkspaceInfo((prev) => {
    return {
      ...prev,
      [part]: e.target.value,
    };
  });
};

const handleSubmit = async (
  type,
  workspace_id,
  workspaceInfo,
  handleRefresh,
  dispatch,
  access,
  owner_id,
) => {
  const reqBody = {
    workspace_id,
    ...workspaceInfo,
    access,
    owner_id,
  };
  const { status, error, message } = await postPrompts(reqBody);
  if (status !== STATUS_SUCCESS) {
    errorToastMessage(error, message);
  } else {
    await handleRefresh();
    dispatch(closeModal(type));
  }
};

export default function AddPromptModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspace_id, handleRefresh } = data;

  const [workspaceInfo, setWorkspaceInfo] = useState({
    name: '',
    description: '',
  });

  const [isAccess, setIsAccess] = useState(1);
  const handleIsAccess = useCallback((e) => {
    setIsAccess(+e.target.value);
  }, []);

  // ** 사용자[선택 항목] **
  const userList = useRef([]);
  const handleSelectedUserList = useCallback((selectedList) => {
    userList.current = selectedList;
  }, []);

  const { ownerList, owner, handleOwner } = useOwnerList(
    getPromptOwner,
    workspace_id,
  );

  const isFirstName = useRef(false);
  const isNameValidate = calNameValidate(workspaceInfo.name);
  const isNameInputError = !isNameValidate && isFirstName.current;
  const nameErrorMessage = calNameErrorMsg(
    workspaceInfo.name,
    isNameValidate,
    t,
  );

  return (
    <NewStyleModalFrame
      title={t('prompt.create.label')}
      type={type}
      submit={{
        text: t('onlyNext.label'),
        func: () =>
          handleSubmit(
            type,
            workspace_id,
            workspaceInfo,
            handleRefresh,
            dispatch,
            isAccess,
            owner.value,
          ),
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={isNameValidate && owner.label}
      isResize={true}
      isMinimize={true}
      footerMessage={nameErrorMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('prompt.name.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('prompt.name.placeholder')}
            onChange={(e) => {
              isFirstName.current = true;
              handleInput(e, 'name', setWorkspaceInfo);
            }}
            name='workspace'
            value={workspaceInfo.name}
            status={isNameInputError ? 'error' : 'default'}
            isReadOnly={type === 'EDIT_WORKSPACE'}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <InputBoxWithLabel
        labelText={t('prompt.desc.label')}
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
      >
        <Textarea
          size='large'
          placeholder={t('prompt.desc.placeholder')}
          value={workspaceInfo.description}
          name='description'
          onChange={(e) => handleInput(e, 'description', setWorkspaceInfo)}
          customStyle={{ fontSize: '14px', height: '160px' }}
          isShowMaxLength
        />
      </InputBoxWithLabel>
      <AccessOwnerSelect
        isAccess={isAccess}
        handleInputs={handleIsAccess}
        ownerValue={owner?.value}
        ownerList={ownerList}
        handleOwner={handleOwner}
      />
      {isAccess === 0 && (
        <MultiSelect
          label='users.label'
          listLabel='availableUsers.label'
          selectedLabel='chosenUsers.label'
          list={ownerList}
          selectedList={[]}
          onChange={({ selectedList }) => handleSelectedUserList(selectedList)}
          exceptItem={owner && owner.value}
          optional
          style={{ marginTop: '32px' }}
        />
      )}
    </NewStyleModalFrame>
  );
}
