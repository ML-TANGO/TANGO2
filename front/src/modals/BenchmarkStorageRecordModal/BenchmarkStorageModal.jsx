import { useState, useEffect, useCallback } from 'react';
import dayjs from 'dayjs';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import BenchmarkStorageRecordModalContent from '@src/components/modalContents/BenchmarkStorageRecordModalContent/BenchmarkStorageRecordModalContent';
import { toast } from '@src/components/Toast';

// Utils
import { errorToastMessage } from '@src/utils';

// Network
import { callApi, download, STATUS_SUCCESS } from '@src/network';

function BenchmarkStorageModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const { nodeId, storageId, nodeName, storageName } = modalData.data;
  const [testHistory, setTestHistory] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  /**
   * 기록 데이터 가져오기
   */
  const getData = useCallback(async () => {
    setIsLoading(true);
    const response = await callApi({
      url: `benchmark/storage-cell-info?node_id=${nodeId}&storage_id=${storageId}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (result) {
        setTestHistory(result);
      }
    } else {
      errorToastMessage(error, message);
    }
    setIsLoading(false);
  }, [nodeId, storageId]);

  /**
   * CSV 다운로드
   * @returns
   */
  const csvDownloadRecord = async () => {
    const response = await download({
      url: `benchmark/storage-cell-info/csv-download?node_id=${nodeId}&storage_id=${storageId}`,
      method: 'GET',
      responseType: 'blob',
    });

    const { data, status } = response;
    const { message, error } = data;
    if (status === 200) {
      if (error) {
        const { code, location } = error;
        toast.error(t(`${location}.${code}.toast`));
      }
      const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `[Benchmark-storage] ${nodeName}-${storageName} ${dayjs().format(
        'YYYYMMDD hhmmss',
      )}.csv`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      toast.error(message);
    }
    return response;
  };

  useEffect(() => {
    getData();
  }, [getData]);

  return (
    <BenchmarkStorageRecordModalContent
      type={type}
      modalData={modalData}
      testHistory={testHistory}
      isLoading={isLoading}
      csvDownloadRecord={csvDownloadRecord}
      onReloadData={getData}
    />
  );
}

export default BenchmarkStorageModal;
