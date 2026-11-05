import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-toastify';

import { getUsers } from '@src/apis/flightbase/options';
import { STATUS_SUCCESS } from '@src/network';

const calLabelObj = (type, t) => {
  if (type === 'user')
    return {
      title: t('user.label'),
      firstLabel: t('availableUsers.label'),
      secondLabel: t('chosenUsers.label'),
      placeholder: t('inputUser.label'),
    };

  return {
    title: t('workspace'),
    firstLabel: t('availableWorkspaces.label'),
    secondLabel: t('chosenWorkspaces.label'),
    placeholder: t('workspaceSearch.placeholder'),
  };
};

const useAssignment = ({ type, workspaceId }) => {
  const { t } = useTranslation();

  const [userList, setUserList] = useState([]);
  const [selectedUserList, setSelectedUserList] = useState([]);
  const [pickUserList, setPickUserList] = useState(new Map());

  const { title, firstLabel, secondLabel, placeholder } = calLabelObj(type, t);

  const handlePickUser = useCallback(
    (user) => {
      const newPickedUser = new Map(pickUserList);
      const getIsPickValue = newPickedUser.get(user.id);

      if (getIsPickValue) {
        newPickedUser.delete(user.id);
      } else {
        newPickedUser.set(user.id, user);
      }

      setPickUserList(newPickedUser);
    },
    [pickUserList],
  );

  useEffect(() => {
    const getUserList = async () => {
      const { result, status, message } = await getUsers(workspaceId);

      if (status === STATUS_SUCCESS) {
        setUserList(result);
      } else {
        toast.error(message);
      }
    };
    getUserList(setUserList);
  }, [workspaceId]);

  return {
    title,
    firstLabel,
    secondLabel,
    placeholder,
    userList,
    handlePickUser,
  };
};

export default useAssignment;
