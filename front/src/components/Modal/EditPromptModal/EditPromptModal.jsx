import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText, Textarea } from '@jonathan/ui-react';

import AccessOwnerSelect from '@src/components/molecules/AccessOwnerSelect';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import { getPromptOwner } from '@src/apis/llm/prompt';
import useOwnerList from '@src/hooks/useOwnerList';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './EditPromptModal.module.scss';

const cx = classNames.bind(style);

export default function EditPromptModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workspace_id, handleRefresh } = data;

  const { prompt_item } = data;
  const { name, description, access, owner: editOwner } = prompt_item;

  const [workspaceInfo, setWorkspaceInfo] = useState({
    name,
    description,
  });

  const handleWorkspaceInfo = useCallback((e, name) => {
    setWorkspaceInfo((prev) => ({
      ...prev,
      [name]: e.target.value,
    }));
  }, []);

  const [isAccess, setIsAccess] = useState(access);
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

  useEffect(() => {
    const ownerValue = ownerList.find(({ label }) => label === editOwner);
    handleOwner(ownerValue);
  }, [editOwner, handleOwner, ownerList]);

  return (
    <NewStyleModalFrame
      title={t('prompt.edit.label')}
      type={type}
      submit={{
        text: t('update.label'),
        func: () => {},
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={true}
      isResize={true}
      isMinimize={true}
      footerMessage={''}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('prompt.name.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('prompt.name.placeholder')}
            onChange={() => {}}
            name='workspace'
            value={name}
            isReadOnly={true}
            options={{ maxLength: 50 }}
            autoFocus={true}
            customStyle={{ fontSize: '14px' }}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
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
            onChange={(e) => handleWorkspaceInfo(e, 'description')}
            customStyle={{ fontSize: '14px', height: '160px' }}
            isShowMaxLength
          />
        </InputBoxWithLabel>
      </div>
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
