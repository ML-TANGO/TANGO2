import { loadModalComponent } from '@src/modal';
import { useEffect, useRef, useState } from 'react';

import AdminStorageContent from '@src/components/pageContents/admin/AdminStorageContent';

import { callApi, STATUS_SUCCESS } from '@src/network';
import { errorToastMessage } from '@src/utils';

const defaultStorage = {
  usage: {
    alloc: 0,
    used: 0,
    size: 0,
  },
  fstype: null,
  name: '-',
  workspaces: {
    main: [
      { alloc_size: 0, used_size: 0, workspace_name: '-' },
      { alloc_size: 0, used_size: 0, workspace_name: '-' },
    ],
    data: [
      { alloc_size: 0, used_size: 0, workspace_name: '-' },
      { alloc_size: 0, used_size: 0, workspace_name: '-' },
    ],
  },
};

const initialData = {
  storageDataList: [defaultStorage],
  total: {
    total_size: 0,
    total_alloc: 0,
    total_used: 0,
  },
};

const getStorageData = async (setStorageList, isLoadingRef) => {
  if (isLoadingRef.current) return;
  isLoadingRef.current = true;

  const { status, result, error, message } = await callApi({
    url: 'storage',
    method: 'get',
  });

  if (status === STATUS_SUCCESS) {
    const { total_size, total_alloc, total_used } = result.total;
    setStorageList({
      storageDataList: result.list,
      total: {
        total_size: total_size,
        total_alloc: total_alloc,
        total_used: total_used,
      },
    });
  } else {
    setStorageList(initialData);
    errorToastMessage(error, message);
  }
  isLoadingRef.current = false;
};

function AdminStoragePage() {
  const [storageList, setStorageList] = useState(initialData);
  const { storageDataList, total } = storageList;

  const isMountRef = useRef(false);
  const isLoadingRef = useRef(false);

  useEffect(() => {
    loadModalComponent('ADD_STORAGE');
    loadModalComponent('SETTING_STORAGE');

    isMountRef.current = true;
    getStorageData(setStorageList, isLoadingRef);
    const interval = setInterval(
      () => getStorageData(setStorageList, isLoadingRef),
      5000,
    );

    return () => {
      clearInterval(interval);
      isMountRef.current = false;
      isLoadingRef.current = false;
    };
  }, []);

  return (
    <AdminStorageContent
      totalData={
        isLoadingRef.current || !isMountRef.current ? initialData.total : total
      }
      storageDataList={
        isLoadingRef.current || !isMountRef.current
          ? initialData.storageDataList
          : storageDataList
      }
      isMountRef={isMountRef}
      isLoadingRef={isLoadingRef}
    />
  );
}

export default AdminStoragePage;
