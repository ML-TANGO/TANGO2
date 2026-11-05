import { loadModalComponent } from '@src/modal';
import dayjs from 'dayjs';
import { debounce } from 'lodash';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

// Components
import AdminBenchmarkingContent from '@src/components/pageContents/admin/AdminBenchmarkingContent';
import { toast } from '@src/components/Toast';

// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, download, STATUS_SUCCESS } from '@src/network';
// Utils
import { convertBps, errorToastMessage } from '@src/utils';

function AdminBenchmarkingPage({ trackingEvent }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const [nodeSyncAll, setNodeSyncAll] = useState(false);
  const [storageSyncAll, setStorageSyncAll] = useState(false);
  const [nodeList, setNodeList] = useState([]);
  const [storageList, setStorageList] = useState([]);
  const [networkGroupList, setNetworkGroupList] = useState([]);
  const [showNetworkCount, setShowNetworkCount] = useState(0);
  const [nodeResultObj, setNodeResultObj] = useState({});
  const [storageResultObj, setStorageResultObj] = useState({});
  const storageDataKeyList = [
    'read_withbuffer_iops',
    'read_withbuffer_speed',
    'read_withoutbuffer_iops',
    'read_withoutbuffer_speed',
    'write_withbuffer_iops',
    'write_withbuffer_speed',
    'write_withoutbuffer_iops',
    'write_withoutbuffer_speed',
  ]; // 백엔드에서 오는 순서가 바뀔 가능성이 있어서 순서를 미리 정의함

  /**
   * 테이블 정보 - 노드 정보, 네트워크 그룹 이름, 스토리지 정보
   */
  const getNodeInfo = useCallback(async () => {
    const response = await callApi({
      url: 'benchmark/basic-node-info',
      method: 'GET',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setNodeList(result?.node_list || []);
      setStorageList(result?.storage_list || []);
      let networkList = result?.network_group_list || [];
      networkList = networkList.map((v) => {
        return { ...v, selected: true };
      });
      setNetworkGroupList(networkList);
      setShowNetworkCount(networkList.length);
      const isLatestNodeResult = await getNodeResultInfo(true);
      const isLatestStorageResult = await getStorageResultInfo(true);
      if (!isLatestNodeResult || !isLatestStorageResult) {
        toast.success(t('benchmark.info.message'));
      }
    } else {
      errorToastMessage(error, message);
    }
    return response;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  /**
   * 네트워크 그룹 이름 선택
   * @param {number} selectedId
   */
  const onSelectNetwork = (selectedId) => {
    const newList = networkGroupList.map(({ id, name, selected }) => {
      if (selectedId === id) {
        selected = !selected;
      }
      return { id, name, selected };
    });
    setNetworkGroupList(newList);
    // 그룹 선택 변경에 따라 보여줄 컬럼 개수 저장
    setShowNetworkCount(newList.filter(({ selected }) => selected).length);
  };

  /**
   * 노드 테스트 요청 (동기화)
   * @param {Boolean} isSelectAll 전체선택 여부
   * @param {Number} selectLine 선택한 서버 라인 id
   * @param {Object} selectCell 선택한 셀의 클라이언트/서버 id
   * @returns
   */
  const nodeRequestCheck = async (
    isSelectAll = false,
    selectLine = 0,
    selectCell = {},
  ) => {
    const response = await callApi({
      url: 'benchmark/network-bandwidth-check',
      method: 'POST',
      body: {
        select_all: isSelectAll,
        select_line: selectLine,
        select_cell: selectCell,
      },
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getNodeResultInfo(false, isSelectAll);
    } else {
      errorToastMessage(error, message);
    }
    return response;
  };

  /**
   * 스토리지 테스트 요청 (동기화)
   * @param {Boolean} isSelectAll 전체선택 여부
   * @param {Number} selectNode 선택한 노드 id
   * @param {Number} selectStorage 선택한 스토리지 id
   * @param {Object} selectCell 선택한 셀의 노드/스토리지 id
   * @returns
   */
  const storageRequestCheck = async (
    isSelectAll = false,
    selectNode = 0,
    selectStorage = 0,
    selectCell = {},
  ) => {
    const response = await callApi({
      url: 'benchmark/storage-fio-check',
      method: 'POST',
      body: {
        select_all: isSelectAll,
        select_cell: selectCell,
        select_node: selectNode,
        select_storage: selectStorage,
      },
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getStorageResultInfo(false, isSelectAll);
    } else {
      errorToastMessage(error, message);
    }
    return response;
  };

  /**
   * 노드 테스트 결과 값 받아오기
   * @param {boolean} isFirst 페이지 첫 진입시 가장 최근 데이터 가져오는지 여부
   * @param {boolean} isSelectAll 전체 동기화 여부
   * @returns
   */
  const getNodeResultInfo = async (isFirst, isSelectAll) => {
    const response = await callApi({
      url: 'benchmark/node-network-all-latest-info',
      method: 'GET',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      let isRunningCount = 0;
      for (let i = 0; i < result.length; i++) {
        const clientNodeId = result[i].client_node_id;
        const serverNodeId = result[i].server_node_id;
        const networkGroup = result[i].network_group;
        const tmpObj = nodeResultObj;
        if (result[i].is_running) {
          setNodeSyncAll(isSelectAll);
          isRunningCount++;
          networkGroup.map((item) => {
            const {
              client_node_interface: clientNodeInterface,
              server_node_interface: serverNodeInterface,
              client_network_group_name: clientNetworkGroupName,
              server_network_group_name: serverNetworkGroupName,
            } = item;
            const key = `${clientNodeId}-${serverNodeId}-${clientNetworkGroupName}-${serverNetworkGroupName}-${clientNodeInterface}-${serverNodeInterface}`;
            if (clientNetworkGroupName === serverNetworkGroupName) {
              tmpObj[key] = 'syncing';
            } else {
              tmpObj[key] = '';
            }
            return tmpObj;
          });
        } else {
          networkGroup.map((item) => {
            const {
              client_node_interface: clientNodeInterface,
              server_node_interface: serverNodeInterface,
              client_network_group_name: clientNetworkGroupName,
              server_network_group_name: serverNetworkGroupName,
              bandwidth,
              error_message: errorMessage,
            } = item;
            const key = `${clientNodeId}-${serverNodeId}-${clientNetworkGroupName}-${serverNetworkGroupName}-${clientNodeInterface}-${serverNodeInterface}`;
            if (errorMessage) {
              tmpObj[key] = `[Error] ${errorMessage}`;
            } else {
              tmpObj[key] = bandwidth ? convertBps(bandwidth) : '';
            }
            return tmpObj;
          });
        }
        setNodeResultObj({ ...tmpObj });
      }
      if (isRunningCount > 0) {
        debounceGetNodeResultInfo(isFirst, isSelectAll);
      } else {
        if (isFirst) {
          toast.success(t('benchmark.latestData.complete.message'));
        } else if (isSelectAll) {
          setNodeSyncAll(false);
          toast.success(
            t('benchmark.syncAll.complete.message', {
              target: t('node.label'),
            }),
          );
        } else {
          toast.success(t('benchmark.sync.complete.message'));
        }
      }
      return true;
    } else {
      errorToastMessage(error, message);
    }
    return false;
  };

  /**
   * 스토리지 결과값 받아오기
   * @param {boolean} isFirst 페이지 첫 진입시 가장 최근 데이터 가져오는지 여부
   * @param {boolean} isSelectAll 전체 동기화 여부
   * @returns
   */
  const getStorageResultInfo = async (isFirst, isSelectAll) => {
    const response = await callApi({
      url: 'benchmark/storage-all-info',
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      let isRunningCount = 0;
      for (let i = 0; i < result.length; i++) {
        const tmpObj = storageResultObj;
        const nodeId = result[i].node_id;
        const storageId = result[i].storage_id;
        if (result[i].is_running) {
          setStorageSyncAll(isSelectAll);
          isRunningCount++;
          storageDataKeyList.map((key) => {
            return (tmpObj[`${nodeId}-${storageId}-${key}`] = 'syncing');
          });
        } else {
          const errorMessage = result[i].data.error_message;
          if (errorMessage) {
            tmpObj[`${nodeId}-${storageId}-error`] = `[Error] ${errorMessage}`;
          }
          storageDataKeyList.map((key) => {
            if (key.indexOf('speed') !== -1) {
              return (tmpObj[`${nodeId}-${storageId}-${key}`] = result[i].data[
                key
              ]
                ? convertBps(result[i].data[key], 'byte')
                : '-');
            }
            return (tmpObj[`${nodeId}-${storageId}-${key}`] =
              result[i].data[key] || '-');
          });
        }
        setStorageResultObj({ ...tmpObj });
      }
      if (isRunningCount > 0) {
        debounceGetStorageResultInfo(isFirst, isSelectAll);
      } else {
        if (!isFirst) {
          if (isSelectAll) {
            setStorageSyncAll(false);
            toast.success(
              t('benchmark.syncAll.complete.message', {
                target: t('storage.label'),
              }),
            );
          } else {
            toast.success(t('benchmark.sync.complete.message'));
          }
        }
      }
      return true;
    } else {
      errorToastMessage(error, message);
    }
    return false;
  };

  const debounceGetNodeResultInfo = debounce((isFirst, isSelectAll) => {
    getNodeResultInfo(isFirst, isSelectAll);
  }, 300);

  const debounceGetStorageResultInfo = debounce((isFirst, isSelectAll) => {
    getStorageResultInfo(isFirst, isSelectAll);
  }, 300);

  /**
   * CSV 다운로드
   * @param {string} 'node' || 'storage'
   * @returns
   */
  const csvDownloadTable = async (target) => {
    let url = 'benchmark/node-network-all-latest-info/csv-download'; // node
    if (target === 'storage') {
      url = 'benchmark/storage-all-info/csv-download';
    }
    const response = await download({
      url,
      method: 'GET',
      responseType: 'blob',
    });

    const { data, status } = response;
    const { message, error } = data;
    if (status === 200) {
      if (error) {
        errorToastMessage(error, message);
      }
      const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `[Benchmark-${target}] ${dayjs().format(
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

  const openNodeRecordModal = (
    clientNodeId,
    serverNodeId,
    clientNodeName,
    serverNodeName,
  ) => {
    dispatch(
      openModal({
        modalType: 'BENCHMARK_NODE_RECORD',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('BENCHMARK_NODE_RECORD'));
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: { clientNodeId, serverNodeId, clientNodeName, serverNodeName },
        },
      }),
    );
    trackingEvent({
      category: 'Admin Benchmarking Page',
      action: 'Open Benchmarking Node Record Modal',
    });
  };

  const openStorageRecordModal = (nodeId, storageId, nodeName, storageName) => {
    dispatch(
      openModal({
        modalType: 'BENCHMARK_STORAGE_RECORD',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('BENCHMARK_STORAGE_RECORD'));
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: { nodeId, storageId, nodeName, storageName },
        },
      }),
    );
    trackingEvent({
      category: 'Admin Benchmarking Page',
      action: 'Open Benchmarking Storage Record Modal',
    });
  };

  useEffect(() => {
    loadModalComponent('BENCHMARK_NODE_RECORD');
    loadModalComponent('BENCHMARK_STORAGE_RECORD');
  }, []);

  useEffect(() => {
    getNodeInfo();
  }, [getNodeInfo]);

  return (
    <AdminBenchmarkingContent
      nodeList={nodeList}
      storageList={storageList}
      nodeSyncAll={nodeSyncAll}
      storageSyncAll={storageSyncAll}
      networkGroupList={networkGroupList}
      showNetworkCount={showNetworkCount}
      nodeResultObj={nodeResultObj}
      storageResultObj={storageResultObj}
      storageDataKeyList={storageDataKeyList}
      nodeRequestCheck={nodeRequestCheck}
      storageRequestCheck={storageRequestCheck}
      onSelectNetwork={onSelectNetwork}
      csvDownloadTable={csvDownloadTable}
      openNodeRecordModal={openNodeRecordModal}
      openStorageRecordModal={openStorageRecordModal}
    />
  );
}

export default AdminBenchmarkingPage;
