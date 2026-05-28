import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory } from 'react-router-dom';

import { InputText, Textarea } from '@jonathan/ui-react';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';

import {
  getPlaygroundOwner,
  putDescription,
  putPlaygrounds,
} from '@src/apis/llm/playground';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './EditPlaygroundModal.module.scss';

const cx = classNames.bind(style);

const accessOption = [
  {
    label: 'public',
    value: 1,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
  {
    label: 'private',
    value: 0,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
];

const handleSubmit = async ({
  type,
  playgroundInfo,
  selectedAccessType,
  owner,
  editUserList,
  handleRefresh,
  dispatch,
}) => {
  const reqBody = {
    playground_id: playgroundInfo.id,
    description: playgroundInfo.description,
    access: selectedAccessType,
    owner_id: owner.value,
    users_id: editUserList,
  };
  const { status, error, message } = await putPlaygrounds(reqBody);
  if (status !== STATUS_SUCCESS) {
    errorToastMessage(error, message);
  } else {
    await handleRefresh();
    dispatch(closeModal(type));
  }
};

const handleInput = (e, part, setPlaygroundInfo) => {
  setPlaygroundInfo((prev) => {
    return {
      ...prev,
      [part]: e.target.value,
    };
  });
};

const EditPlaygroundModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const history = useHistory();

  const { workspace_id, playground_data, handleRefresh, isAccess, userList } =
    data;

  const { userName: loggedInUserName } = useSelector(
    (state) => state.auth,
    shallowEqual,
  );
  const [playgroundInfo, setPlaygroundInfo] = useState({
    id: playground_data.id,
    name: playground_data.title,
    description: playground_data.subTitle,
  });

  const [selectedAccessType, setSelectedAccessType] = useState(isAccess);
  const [owner, setOwner] = useState({ label: '', value: '' });
  const [ownerList, setOwnerList] = useState([]);

  const handleOwner = ({ value, label }) => {
    setOwner({ label, value });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedAccessType(Number(value));
  };

  const [editUserList, setUserList] = useState([]);
  const handleUserList = ({ selectedList }) => {
    const copyList = selectedList.slice();
    const transformList = copyList.map((info) => info.value);
    setUserList(transformList);
  };

  useEffect(() => {
    const fetchOwnerList = async () => {
      const res = await getPlaygroundOwner(workspace_id);
      const { result, status } = res;

      if (status === STATUS_SUCCESS) {
        const ownerList = result.map(({ id, name }) => ({
          value: id,
          label: name,
        }));
        const filterList = ownerList.filter((item1) => {
          return !userList.some((item2) => item1.value === item2.value);
        });
        setOwnerList(filterList);
        const playgroundOwner = result.filter(
          ({ name }) => name === playground_data.constructor,
        )[0];
        setOwner({
          label: playgroundOwner.name,
          value: playgroundOwner.id,
        });
      }
    };

    fetchOwnerList();
  }, [playground_data, userList, workspace_id]);

  return (
    <NewStyleModalFrame
      title={t('playground.edit.label')}
      type={type}
      submit={{
        text: t('edit.label'),
        func: () =>
          handleSubmit({
            type,
            playgroundInfo,
            selectedAccessType,
            owner,
            editUserList,
            handleRefresh,
            dispatch,
          }),
      }}
      cancel={{
        text: t('cancel.label'),
      }}
      validate={true}
      isResize={true}
      isMinimize={true}
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
              handleInput(e, 'name', setPlaygroundInfo);
            }}
            name='workspace'
            value={playgroundInfo.name}
            isReadOnly={type === 'EDIT_PLAYGROUND'}
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
          value={playgroundInfo.description}
          name='description'
          onChange={(e) => handleInput(e, 'description', setPlaygroundInfo)}
          customStyle={{ fontSize: '14px', height: '160px' }}
          isShowMaxLength
        />
      </InputBoxWithLabel>
      <div className={cx('bottom-box')}>
        <div className={cx('content')}>
          <InputBoxWithLabel
            labelText={t('accessType.label')}
            labelSize='large'
            disableErrorMsg
          >
            <FbRadio
              name='accessType'
              options={accessOption}
              value={selectedAccessType}
              onChange={(e) => {
                radioBtnHandler('accessType', e.currentTarget.value);
              }}
              isLabelColor
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('content')}>
          <InputBoxWithLabel
            labelText={t('owner.label')}
            labelSize='large'
            disableErrorMsg
          >
            <GrayDropDown
              list={ownerList}
              value={owner}
              handleSelectOption={handleOwner}
              placeholder={t('owner.placeholder')}
              isCloseBorder={false}
              listCustomStyle={{ maxHeight: '110px', overflow: 'auto' }}
              isReadOnly={loggedInUserName !== playground_data.constructor}
            />
          </InputBoxWithLabel>
        </div>
      </div>
      {selectedAccessType === 0 && (
        <MultiSelect
          label='users.label'
          listLabel='availableUsers.label'
          selectedLabel='chosenUsers.label'
          list={ownerList} // 초기 목록
          selectedList={userList} // 초기 선택된 목록
          onChange={handleUserList} // 변경 이벤트
          exceptItem={owner && owner.value}
          optional
          style={{ marginTop: '32px' }}
        />
      )}
    </NewStyleModalFrame>
  );
};

export default EditPlaygroundModal;
