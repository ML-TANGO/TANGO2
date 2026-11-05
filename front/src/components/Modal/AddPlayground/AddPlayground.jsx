import { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory } from 'react-router-dom';

import { InputText, Textarea } from '@jonathan/ui-react';

import AccessOwnerSelect from '@src/components/molecules/AccessOwnerSelect';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import { getPlaygroundOwner, postPlayground } from '@src/apis/llm/playground';
import { closeModal } from '@src/store/modules/modal';
import useOwnerList from '@src/hooks/useOwnerList';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './AddPlayground.module.scss';

const cx = classNames.bind(style);

const list = [];

export const playgroundNameExg =
  /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;

// ! 제거 필요
export const calNameValidate = (name) => {
  if (!name) return false;
  const isNameValidate = !playgroundNameExg.test(name);
  return isNameValidate;
};

// ! 제거 필요
export const calNameErrorMsg = (name, isNameValidate, t) => {
  if (!name) return t('nickname.empty.message');
  if (!isNameValidate) return t('newNameRule.message');
  return '';
};

export const calNameError = (name) => {
  const isNameError = playgroundNameExg.test(name);
  if (isNameError) return true;
  return false;
};

export const calFooterMessage = (name, isNameError) => {
  if (!name) return '이름을 입력해 주세요.';
  if (isNameError)
    return '이름을 확인해주세요 (제외문자 :한글, !?*<>#^$%&(){}[]`\':;/"|\\ 및 공백)';
  return '';
};

const handleSubmit = async (
  type,
  workspace_id,
  workspaceInfo,
  handleRefresh,
  dispatch,
  history,
  access,
  owner_id,
  userList,
) => {
  const reqBody = {
    workspace_id,
    ...workspaceInfo,
    access,
    owner_id,
    user_id: userList,
  };
  const { name, description } = workspaceInfo;
  const { status, error, message } = await postPlayground(reqBody);
  if (status !== STATUS_SUCCESS) {
    errorToastMessage(error, message);
  } else {
    const playgroundList = await handleRefresh();
    const findPlaygroundItem = playgroundList.find(
      (el) => el.title === name && el.subTitle === description,
    );
    const playgroundItemId = findPlaygroundItem.id;
    history.push(
      `/user/workspace/${workspace_id}/llmplayground/${playgroundItemId}/llmplayground`,
    );
    dispatch(closeModal(type));
  }
};

const handleInput = (e, part, setWorkspaceInfo) => {
  setWorkspaceInfo((prev) => {
    return {
      ...prev,
      [part]: e.target.value,
    };
  });
};

const AddPlayground = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();
  const { workspace_id, handleRefresh } = data;

  const [workspaceInfo, setWorkspaceInfo] = useState({
    name: null,
    description: '',
  });
  const isNameError = calNameError(workspaceInfo.name);

  const [isAccess, setIsAccess] = useState(1);
  const handleIsAccess = useCallback((e) => {
    setIsAccess(+e.target.value);
  }, []);

  const { ownerList, owner, handleOwner } = useOwnerList(
    getPlaygroundOwner,
    workspace_id,
  );

  // ** 사용자[선택 항목] **
  const userList = useRef([]);
  const handleSelectedUserList = useCallback((selectedList) => {
    const transformList = selectedList.map((info) => info.value);
    userList.current = transformList;
  }, []);

  const footerMessage = calFooterMessage(workspaceInfo.name, isNameError);
  const isValidate = !footerMessage;

  // const {
  //   title,
  //   firstLabel,
  //   secondLabel,
  //   placeholder,
  //   userList: userList2,
  //   handlePickUser,
  // } = useAssignment({
  //   type: 'user',
  //   workspaceId: workspace_id,
  // });

  return (
    <NewStyleModalFrame
      title={t('playground.add.label')}
      type={type}
      submit={{
        text: t('onlyNext.label'),
        func: async () =>
          await handleSubmit(
            type,
            workspace_id,
            workspaceInfo,
            handleRefresh,
            dispatch,
            history,
            isAccess,
            owner.value,
            userList.current,
          ),
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={isValidate}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('playground.name.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            placeholder={t('playground.add.name.placeholder')}
            onChange={(e) => {
              handleInput(e, 'name', setWorkspaceInfo);
            }}
            name='workspace'
            value={workspaceInfo.name}
            status={
              isNameError || workspaceInfo.name === '' ? 'error' : 'default'
            }
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
        labelText={t('playground.add.desc.label')}
        optionalText={t('optional.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
      >
        <Textarea
          size='large'
          placeholder={t('playground.add.desc.placeholder')}
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
          selectedList={list}
          onChange={({ selectedList }) => handleSelectedUserList(selectedList)}
          exceptItem={owner && owner.value}
          optional
          style={{ marginTop: '32px' }}
        />
      )}
      {/* <UserAssignment
        title={title}
        firstLabel={firstLabel}
        secondLabel={secondLabel}
        placeholder={placeholder}
        list={userList2}
        selectedList={[]}
        handlePickUser={handlePickUser}
      /> */}
    </NewStyleModalFrame>
  );
};

export default AddPlayground;
