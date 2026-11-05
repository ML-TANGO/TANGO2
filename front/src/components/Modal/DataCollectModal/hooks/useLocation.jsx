import { useCallback, useEffect, useState } from 'react';
import { toast } from 'react-toastify';

import { getCollectOtionsDirList } from '@src/apis/flightbase/dataset/collect';
import { STATUS_SUCCESS } from '@src/network';

const getFolderList = async (
  datasetId,
  folderListLoading,
  setFolderList,
  setFolderListLoading,
) => {
  if (folderListLoading) return;
  setFolderListLoading(true);
  const { result, status, message } = await getCollectOtionsDirList(datasetId);
  if (status === STATUS_SUCCESS) {
    const transformList = result.map((name) => ({
      id: name,
      name,
    }));
    setFolderList(transformList);
  } else {
    toast.error(message);
  }
  setFolderListLoading(false);
};

const useLocation = (initDatasetValue, initFolderValue) => {
  const [datasetList, setDatasetList] = useState([]);
  const [folderList, setFolderList] = useState([]);

  const [selectedLocationValue, setSelectedLocationValue] = useState({
    datasetValue: {
      id: initDatasetValue,
      name: undefined,
    },
    folderValue: {
      id: initFolderValue,
      name: undefined,
    },
  });
  const { datasetValue, folderValue } = selectedLocationValue;

  const handleSelectedLocation = useCallback((name, value) => {
    setSelectedLocationValue((prev) => ({
      ...prev,
      [name]: value,
    }));
  }, []);

  const [folderListLoading, setFolderListLoading] = useState(false);
  useEffect(() => {
    if (!datasetValue.id) return;
    getFolderList(
      datasetValue.id,
      folderListLoading,
      setFolderList,
      setFolderListLoading,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetValue]);

  return {
    datasetList,
    folderList,
    datasetValue,
    folderValue,
    folderListLoading,
    setDatasetList,
    handleSelectedLocation,
  };
};

export default useLocation;
