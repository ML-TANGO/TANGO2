import { useState, useEffect, useCallback } from 'react';
import dayjs from 'dayjs';

// i18n
import { useTranslation } from 'react-i18next';

// Components
import BenchmarkNodeRecordModalContent from '@src/components/modalContents/BenchmarkNodeRecordModalContent/BenchmarkNodeRecordModalContent';
import { toast } from '@src/components/Toast';

// Utils
import { isEmptyObject } from '@src/utils';

// Network
import { callApi, download, STATUS_SUCCESS } from '@src/network';

function BenchmarkNodeRecordModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const { clientNodeId, serverNodeId, clientNodeName, serverNodeName } =
    modalData.data;
  const [testHistory, setTestHistory] = useState(null);
  const [networkGroupList, setNetworkGroupList] = useState([]);
  const [selectedNetworkInfo, setSelectedNetworkInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  /**
   * 기록 데이터 가져오기
   */
  const getData = useCallback(async () => {
    setIsLoading(true);
    const response = await callApi({
      url: `benchmark/node-network-cell-detail-info?client_node_id=${clientNodeId}&server_node_id=${serverNodeId}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      if (result) {
        const { test_history: history, network_group_list: network } = result;
        const networkList = network.map((v, idx) => {
          // 디폴트 선택: 마지막 네트워크 그룹
          const selected = idx === network.length - 1;
          if (selected) {
            setSelectedNetworkInfo(v);
          }
          return { ...v, idx, selected };
        });
        setTestHistory(history);
        setNetworkGroupList(networkList);
      }
    } else {
      if (!isEmptyObject(error)) {
        const { code, location } = error;
        toast.error(t(`${location}.${code}.toast`));
      } else {
        toast.error(message);
      }
    }
    setIsLoading(false);
  }, [clientNodeId, serverNodeId, t]);

  /**
   * CSV 다운로드
   * @returns
   */
  const csvDownloadRecord = async () => {
    const response = await download({
      url: `benchmark/node-network-cell-detail-info/csv-download?client_node_id=${clientNodeId}&server_node_id=${serverNodeId}`,
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
      link.download = `[Benchmark-node] ${clientNodeName}-${serverNodeName} ${dayjs().format(
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

  /**
   * 네트워크 그룹 이름 선택
   * @param {number} selectedIdx
   */
  const onSelectNetwork = (selectedIdx) => {
    const newList = networkGroupList.map((data) => {
      if (selectedIdx === data.idx) {
        data.selected = true;
        setSelectedNetworkInfo(data);
      } else {
        data.selected = false;
      }
      return { ...data, selected: data.selected };
    });
    setNetworkGroupList(newList);
  };

  useEffect(() => {
    getData();
  }, [getData]);

  return (
    <BenchmarkNodeRecordModalContent
      type={type}
      modalData={modalData}
      testHistory={testHistory}
      isLoading={isLoading}
      networkGroupList={networkGroupList}
      selectedNetworkInfo={selectedNetworkInfo}
      onSelectNetwork={onSelectNetwork}
      csvDownloadRecord={csvDownloadRecord}
      onReloadData={getData}
    />
  );
}

export default BenchmarkNodeRecordModal;
