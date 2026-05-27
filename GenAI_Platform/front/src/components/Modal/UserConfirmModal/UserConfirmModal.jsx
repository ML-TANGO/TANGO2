import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { InputText, Selectbox } from '@jonathan/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import { errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserConfirmModal.module.scss';

const cx = classNames.bind(style);

const initial = {
  userId: '',
  group: null,
  email: '',
  name: '',
  team: '',
  jobTitle: '',
};

const handleUserGroup = (group, setUserInfo) => {
  setUserInfo((prev) => {
    return {
      ...prev,
      group,
    };
  });
};

const UserConfirmModal = ({ data, type }) => {
  const dispatch = useDispatch();
  const { submitText, cancelText, confirmUserId, getUsers } = data;

  const { t } = useTranslation();

  const title = useMemo(() => {
    return t('user.confirm.title');
  }, [t]);

  const [userInfo, setUserInfo] = useState(initial);
  const [groupOptionList, setGroupOptionList] = useState([]);
  const { userId, group, email, name, team, jobTitle } = userInfo;

  const handleRegister = async (id, group, approve) => {
    if (!id) {
      toast.error(t('noData.message'));
      return;
    }

    const { status, message, error } = await callApi({
      url: 'users/register',
      method: 'PUT',
      body: {
        register_id: `${id}`,
        approve,
        usergroup_id: group && group.value,
      },
    });

    if (status === STATUS_SUCCESS) {
      let confirmMessage = 'userRequest.approve.success.message';
      if (!approve) {
        confirmMessage = 'userRequest.reject.success.message';
      }
      toast.success(t(confirmMessage));
      await getUsers();
      dispatch(closeModal(type));
    } else {
      errorToastMessage(error, message);
    }
  };

  useEffect(() => {
    const getRegisterUserInfo = async () => {
      const { result, status } = await callApi({
        url: `users/register/${confirmUserId}`,
        method: 'get',
      });
      const { name, team, nickname, job, email } = result;
      setUserInfo(
        status === STATUS_SUCCESS
          ? {
              userId: name,
              group: null,
              email,
              name: nickname,
              team,
              jobTitle: job,
            }
          : initial,
      );
    };

    const getUserGroupOptions = async () => {
      const { result, status } = await callApi({
        url: 'users/option',
        method: 'get',
      });

      const userOptionList = result.usergroup_list.map((el) => {
        return {
          label: el.name,
          value: el.id,
        };
      });
      setGroupOptionList(status === STATUS_SUCCESS ? userOptionList : []);
    };

    getRegisterUserInfo();
    getUserGroupOptions();

    return () => {
      setUserInfo(initial);
      setGroupOptionList([]);
    };
  }, [confirmUserId]);

  return (
    <NewStyleModalFrame
      title={title}
      submit={{
        text: submitText,
        func: () => handleRegister(confirmUserId, group, true),
      }}
      cancel={{
        text: cancelText,
        func: () => handleRegister(confirmUserId, group, false),
      }}
      type={type}
      xCloseOnly
      isResize={true}
      isMinimize={true}
      validate
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
            value={userId}
            placeholder={t('userID.placeholder')}
            disableLeftIcon
            options={{ maxLength: 32 }}
            autoFocus
            isReadOnly
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
            list={groupOptionList}
            selectedItem={group}
            onChange={(group) => handleUserGroup(group, setUserInfo)}
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
            options={{ maxLength: 33 }}
            disableLeftIcon
            tabIndex='4'
            isReadOnly
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
            value={name}
            placeholder={t('nickname.placeholder')}
            options={{ maxLength: 60 }}
            disableLeftIcon
            tabIndex='4'
            isReadOnly
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
            value={team}
            placeholder={t('affiliation.placeholder')}
            options={{ maxLength: 32 }}
            disableLeftIcon
            tabIndex='5'
            customStyle={{ width: '274px' }}
            isReadOnly
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
            value={jobTitle}
            placeholder={t('position.placeholder')}
            options={{ maxLength: 32 }}
            disableLeftIcon
            tabIndex='6'
            customStyle={{ width: '274px' }}
            isReadOnly
          />
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default UserConfirmModal;
