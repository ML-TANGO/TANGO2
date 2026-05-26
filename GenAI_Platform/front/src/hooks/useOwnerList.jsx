import { useCallback, useEffect, useState } from 'react';
import { shallowEqual, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import { STATUS_SUCCESS } from '@src/network';

const useOwnerList = (getOwnerList, workspaceId) => {
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [ownerList, setOwnerList] = useState([]);
  const [owner, setOwner] = useState(null);

  const handleOwner = useCallback((value) => {
    setOwner(value);
  }, []);

  useEffect(() => {
    const fetchOwnerList = async () => {
      const { result, status, message } = await getOwnerList(workspaceId);

      if (status === STATUS_SUCCESS) {
        setOwnerList(
          result.map(({ id, name }) => ({ value: id, label: name })),
        );

        const loginUser = result.find(({ name }) => name === userName);
        if (loginUser) {
          setOwner({ label: loginUser.name, value: loginUser.id });
        }
      } else {
        toast.error(message);
      }
    };

    fetchOwnerList();
  }, [workspaceId, userName, getOwnerList]);

  return { ownerList, userName, owner, handleOwner };
};

export default useOwnerList;
