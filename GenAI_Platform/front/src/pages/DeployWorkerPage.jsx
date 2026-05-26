import { useCallback, useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useParams } from 'react-router-dom';

import DeployWorkerMemoModalContent from '@src/components/Modal/DeployWorkerMemoModal/DeployWorkerMemoModalContent';
import DeployWorkerMemoModalFooter from '@src/components/Modal/DeployWorkerMemoModal/DeployWorkerMemoModalFooter';
import DeployWorkerMemoModalHeader from '@src/components/Modal/DeployWorkerMemoModal/DeployWorkerMemoModalHeader';
// Component
import DeployWorkerContent from '@src/components/pageContents/user/DeployWorkerContent';
import { toast } from '@src/components/Toast';

import { startPath } from '@src/store/modules/breadCrumb';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
import useIntervalCall from '@src/hooks/useIntervalCall';
// Custom hooks
import useLocalStorage from '@src/hooks/useLocalStorage';
// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function DeployWorkerPage() {
  const { t } = useTranslation();

  // Redux Hooks
  const dispatch = useDispatch();

  // Router Hooks
  const history = useHistory();
  const { id: wid, did } = useParams();

  // Custom Hooks
  const workerStatusInLocalStorage =
    useLocalStorage('worker_status')[0] || 'running';

  // history
  const workerStatus =
    history.location?.workerStatus || workerStatusInLocalStorage;

  // Component State
  const [title, setTitle] = useState('');
  const [workerList, setWorkerList] = useState(null);
  const [overviewList, setOverviewList] = useState({});
  const [workerSettingInfo, setWorkerSettingInfo] = useState([]);
  const [selectedPage, setSelectedPage] = useState(
    workerStatus === 'running' ? 0 : 1,
  );

  const [workerIds, setWorkderIds] = useState([]);
  const [originData, setOriginData] = useState([]);
  const [checkedData, setCheckedData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [toggledClear, setToggledClear] = useState(false);
  const [systemLogLoading, setSystemLogLoading] = useState(false);
  const [downLoading, setDownLoading] = useState(false);
  const [addLoading, setAddLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [instanceType, setInstanceType] = useState('');
  const [searchKey, setSearchKey] = useState({
    label: 'all.label',
    value: 'all',
  });
  const [workerSettingModalOpen, setWorkerSettingModalOpen] = useState(false);
  const [workerStopPopup, setWorkerStopPopup] = useState(null);
  const [workerStopList, setWorkerStopList] = useState([]);
  const [workerSettingValue, setWorkerSettingValue] = useState({});

  /**
   * stopped - worker List get 요청
   */
  const getStoppedData = async () => {
    const response = await callApi({
      url: `deployments/worker?deployment_id=${did}&deployment_worker_running_status=0`,
      method: 'get',
    });
    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setOriginData(result);
      if (searchKey.value === 'all') {
        const filteredList = result.filter(
          (data) =>
            String(data['deployment_worker_id']).includes(keyword) ||
            String(data['description']).includes(keyword),
        );
        setTableData(filteredList);
      } else {
        const filteredList = result.filter((data) =>
          String(data[searchKey.value]).includes(keyword),
        );
        setTableData(filteredList);
      }
    } else {
      errorToastMessage(error, message);
    }
  };

  const systemLogDown = async (wid) => {
    setDownLoading(true);
    const response = await network.callApiWithPromise({
      url: `deployments/worker/system_log_download/${wid}`,
      method: 'GET',
    });

    const { data, status } = response;

    if (status === 200 && data !== 'Not Found Pod') {
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[LOG] Worker ${wid}.txt`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } else {
      toast.error(t('downloadError'));
    }
    setDownLoading(false);
  };

  /**
   * 시스템 로그 데이터 요청
   * @param {Number} wid deployment worker id
   */
  const getSystemLogData = async (wid) => {
    let workerIdsBucket = [...workerIds];
    workerIdsBucket.push(wid);

    setWorkderIds([...workerIdsBucket]);
    setSystemLogLoading(true);
    const response = await callApi({
      url: `deployments/worker/system_log/${wid}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      onSystemLog(wid, result);
    } else {
      errorToastMessage(error, message);
    }

    const newWorkerIds = workerIdsBucket.filter((item) => item !== wid);
    setSystemLogLoading(newWorkerIds.length > 0);
    setWorkderIds([...newWorkerIds]);
  };

  /**
   * Worker Running(0), Stopped(1) 화면 선택 탭
   * @param {number} idx
   */
  const tabHandler = (idx) => {
    setSelectedPage(idx);
  };

  /**
   * Worker List 미리보기 설정, true -> open, false -> close
   * @param {number} workerId
   */
  const overviewHandler = async (workerId) => {
    if (!overviewList[workerId] || overviewList[workerId]) {
      setOverviewList({
        ...overviewList,
        [workerId]: !overviewList[workerId],
      });
    }
  };

  /**
   * 새 워커 설정
   */
  const onNewWorkerSetting = useCallback(async () => {
    const response = await callApi({
      url: `deployments/worker-setting/${did}`,
      method: 'get',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const {
        deployment_type,
        gpu_count,
        gpu_model,
        built_in_model_name,
        training_name,
        docker_image,
        command_run_code,
        checkpoint,
        job_name,
        project_name,
        deployment_name: deploymentName,
        command_arguments,
        environments,
        instance_type,
      } = result;

      setWorkerSettingValue(result);
      setInstanceType(instance_type);
      setTitle(deploymentName);
      breadCrumbHandler(deploymentName);

      setWorkerSettingInfo([
        {
          label: 'modelType.label',
          content: deployment_type,
        },
        {
          label: instance_type === 'NPU' ? 'npuUsage.label' : 'gpuUsage.label',
          content: gpu_count,
        },
        {
          label: instance_type === 'NPU' ? 'npuModel.label' : 'gpuModel.label',
          content: gpu_model,
          value: 'gpu_model',
        },
        // {
        //   label: 'model.label',
        //   content: built_in_model_name,
        // },
        {
          label: 'training.label',
          content: project_name,
        },
        {
          label: 'dockerImage.label',
          content: docker_image,
        },
        {
          label: 'runCode.label',
          content: command_run_code,
        },
        { label: 'parameters.label', content: command_arguments },
        {
          label: 'template.envParam.label',
          content: environments ? environments.join(', ') : '',
        },
        // {
        //   label: 'checkpoint.label',
        //   content: checkpoint,
        // },
        // {
        //   label: 'jobInfo.label',
        //   content: job_name,
        // },
      ]);

      return;
    }
    errorToastMessage(error, message);
  }, [did]);

  /**
   * stopped - delete 요청 핸들러
   * @param {array} checkedData // 체크 된 아이템
   */
  const workerDeleteClickHandler = async (checkedData) => {
    let checkedId = [];
    checkedData.map((data) => checkedId.push(data.deployment_worker_id));
    const response = await callApi({
      url: `deployments/worker`,
      method: 'delete',
      body: {
        deployment_worker_id_list: checkedId.join(', '),
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getStoppedData();
      setCheckedData([]);
      setToggledClear(!toggledClear);
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * stopped - 체크 된 아이템 받아와서 state 바로 변경
   * @param {object} selectedRows
   */
  const onSelect = ({ selectedRows }) => {
    setCheckedData(selectedRows);
  };

  /**
   * stopped - Worker Memo 수정 요청 핸들러
   *  @param {number} workerId
   *  @param {string} desc 이전 메모 내용
   */
  const workerMemoHandler = async (workerId, desc) => {
    const response = await callApi({
      url: `deployments/worker/description`,
      method: 'put',
      body: {
        deployment_worker_id: workerId,
        description: desc,
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getStoppedData();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * stopped - 로그 다운로드 요청 핸들러
   * @param {number} deploymentsId
   * @param {string} workerId
   * @param {boolean} nginx_log
   * @param {boolean} api_log
   */
  const workerDownHandler = async (
    deploymentsId,
    workerId,
    nginx_log,
    api_log,
  ) => {
    let query = `deployment_id=${deploymentsId}&worker_list=${workerId}`;
    if (nginx_log) {
      query = `${query}&nginx_log=True`;
    }
    if (api_log) {
      query = `${query}&api_log=True`;
    }

    const response = await network.callApiWithPromise({
      url: `deployments/download_api_log?${query}`,
      method: 'get',
    });
    const { data, status, statusText, headers } = response;

    if (status === 200) {
      if (data.status === 0) {
        toast.error(data.message);
      } else {
        let fileName;
        const contentDisposition = headers['content-disposition']; // 파일 이름
        if (contentDisposition) {
          const [fileNameMatch] = contentDisposition
            .split(';')
            .filter((str) => str.includes('filename'));
          if (fileNameMatch) {
            [, fileName] = fileNameMatch.split('=');
          }
        }
        downloadFile(data, fileName);
        defaultSuccessToastMessage('download');
      }
    } else {
      toast.error(statusText);
    }
  };

  /**
   * stopped - 로그 다운로드 함수
   * @param {string} Log 로그
   * @param {string} fileName 파일이름
   */
  const downloadFile = (log, fileName) => {
    const blob = new Blob([log]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `[LOG]_${fileName}.tar`;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  /**
   * Worker List 요청
   */
  const getWorkerData = useCallback(async () => {
    const response = await callApi({
      url: `deployments/worker?deployment_id=${did}`,
      method: 'get',
    });

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      setWorkerList([...result]);
      if (
        Object.keys(overviewList).length === 0 &&
        Object.keys(result).length > 0
      ) {
        let initializeOverview = {};
        result.forEach((worker) => {
          if (worker && worker.worker_status.status !== 'stop') {
            initializeOverview = {
              ...initializeOverview,
              [String(worker.deployment_worker_id)]: false,
            };
          }
        });
        if (
          JSON.stringify(initializeOverview) !== JSON.stringify(overviewList)
        ) {
          setOverviewList(initializeOverview);
        }
      }
      return true;
    }
    errorToastMessage(error, message);
    return false;
  }, [did, overviewList]);

  /**
   * Worker 추가 요청
   */
  const addWorker = async () => {
    setAddLoading(true);
    const response = await callApi({
      url: 'deployments/worker',
      method: 'post',
      body: {
        deployment_id: did,
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getWorkerData();
    } else {
      errorToastMessage(error, message);
    }
    setAddLoading(false);
  };

  /**
   * Worker 수정 요청
   */
  const onEdit = async () => {
    dispatch(
      openModal({
        modalType: 'EDIT_WORKER',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              onNewWorkerSetting();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          deploymentId: did,
          workspaceId: wid,
        },
      }),
    );
  };

  /**
   * system log 모달
   */
  const onSystemLog = async (wid, systemData) => {
    const modalType = 'SYSTEM_LOG';

    setWorkerSettingModalOpen(!workerSettingModalOpen);
    const newOpenModalToggle = !workerSettingModalOpen;

    dispatch(
      openModal({
        modalType,
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              dispatch(closeModal(modalType));
            },
          },
          deploymentWorkerId: wid,
          systemLogData: systemData,
          systemLogLoading,
          workerIds,
          systemLogDown,
          downLoading,
          isHideScreenFromProps: newOpenModalToggle,
        },
      }),
    );
  };

  /**
   * Worker 중지 요청
   * @param {number} workerId
   */

  const stopWorkerRequest = async (workerId) => {
    const response = await callApi({
      url: `deployments/worker/stop?deployment_worker_id=${workerId}`,
      method: 'get',
    });

    const { status, message, error } = response;
    if (status !== STATUS_SUCCESS) {
      errorToastMessage(error, message);
    }
    if (status === STATUS_SUCCESS) {
      // setWorkerStopList((prev) => prev.filter((id) => id !== workerId));
    }
  };

  /**
   * Worker 중지 modal handler
   * @param {number} workerId
   */
  const workerStopConfirmPopupHandler = (workerId) => {
    setWorkerStopList((prev) => [...prev, workerId]);
    setWorkerStopPopup(workerId);
  };

  /**
   * Worker Memo 핸들러
   * @param {number} workerId
   * @param {number} prevMemo 이전 메모 내용
   */
  const workerMemoModalHandler = (workerId, prevMemo) => {
    const modalType = 'DEPLOY_WORKER_MEMO';
    dispatch(
      openModal({
        modalType,
        modalData: {
          headerRender: DeployWorkerMemoModalHeader,
          contentRender: DeployWorkerMemoModalContent,
          footerRender: DeployWorkerMemoModalFooter,
          workerId,
          prevMemo,
          submit: (memo) => {
            dispatch(closeModal(modalType));
          },
          memoEdit: (id, desc) => {
            workerMemoHandler(id, desc);
          },
        },
      }),
    );
  };

  /**
   * worker 클릭 시 detail 컴포넌트로 이동
   * @param {number} workerId
   */
  const moveToWorkerDetail = (workerId) => {
    history.push({
      pathname: `/user/workspace/${wid}/deployments/${did}/workers/${workerId}/worker`,
      workerStatus: 'running',
      title,
    });
  };

  /**
   * stopped - 검색 입력 시 List 필터링 핸들러
   * @param {string} value
   */
  const inputValueHandler = (value) => {
    setKeyword(value);
    if (searchKey.value === 'all') {
      const filteredList = originData.filter(
        (data) =>
          String(data['deployment_worker_id']).includes(value) ||
          String(data['description']).includes(value),
      );
      setTableData(filteredList);
    } else {
      const filteredList = originData.filter((data) =>
        String(data[searchKey.value]).includes(value),
      );
      setTableData(filteredList);
    }
  };

  /**
   * stopped - 검색 컬럼 조건에 맞는 입력 필터링 핸들러
   * @param {string} value
   */
  const selectInputHandler = (value) => {
    const newState = {
      label: t(value.label),
      value: value.value,
    };
    setSearchKey(newState);
  };

  /**
   * Action 브래드크럼
   * @param {String} deploymentName
   */
  const breadCrumbHandler = useCallback(
    (deploymentName) => {
      dispatch(
        startPath([
          {
            component: {
              name: 'Serving',
              path: `/user/workspace/${wid}/deployments`,
              t,
            },
          },
          {
            component: {
              name: 'Deployment',
              path: `/user/workspace/${wid}/deployments`,
              t,
            },
          },
          {
            component: {
              name: deploymentName,
              path: `/user/workspace/${wid}/deployments/${did}/dashboard`,
            },
          },
          {
            component: {
              name: 'Worker',
              t,
            },
          },
        ]),
      );
    },
    [did, dispatch, t, wid],
  );

  const openCreateApiCodeModal = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_DEPLOYMENT_API',
        modalData: {
          submit: {
            text: t('create.label'),
            func: () => {
              closeModal('CREATE_DEPLOYMENT_API');
            },
          },
          cancel: {
            text: t('cancel.label'),
          },
        },
      }),
    );
  };

  const cancelWorkerStopId = (workerId) => {
    setWorkerStopList((prev) => prev.filter((id) => id !== workerId));
  };

  // const getDeploymentName = useCallback(async () => {
  //   const response = await callApi({
  //     url: `deployments/deployment_name?deployment_id=${did}`,
  //     method: 'GET',
  //   });
  //   const { status, result, message, error } = response;
  //   if (status === STATUS_SUCCESS) {
  //     setTitle(result);
  //     breadCrumbHandler(result);
  //     return true;
  //   }
  //   errorToastMessage(error, message);
  //   return false;
  // }, [breadCrumbHandler, did]);

  useIntervalCall(getWorkerData, 2000);

  useEffect(() => {
    loadModalComponent('EDIT_WORKER');
    loadModalComponent('SYSTEM_LOG');
    loadModalComponent('DEPLOY_WORKER_MEMO');
    loadModalComponent('CREATE_DEPLOYMENT_API');
  }, []);

  useEffect(() => {
    onNewWorkerSetting();
  }, [onNewWorkerSetting]);

  // useEffect(() => {
  //   getDeploymentName();
  // }, [getDeploymentName]);

  return (
    <DeployWorkerContent
      title={title}
      did={did}
      keyword={keyword}
      tableData={tableData}
      searchKey={searchKey}
      workerIds={workerIds}
      workerList={workerList}
      checkedData={checkedData}
      overviewList={overviewList}
      selectedPage={selectedPage}
      toggledClear={toggledClear}
      workerStopPopup={workerStopPopup}
      systemLogLoading={systemLogLoading}
      workerSettingInfo={workerSettingInfo}
      addLoading={addLoading}
      onEdit={onEdit}
      onSelect={onSelect}
      addWorker={addWorker}
      tabHandler={tabHandler}
      getStoppedData={getStoppedData}
      overviewHandler={overviewHandler}
      getSystemLogData={getSystemLogData}
      workerDownHandler={workerDownHandler}
      inputValueHandler={inputValueHandler}
      stopWorkerRequest={stopWorkerRequest}
      selectInputHandler={selectInputHandler}
      moveToWorkerDetail={moveToWorkerDetail}
      workerMemoModalHandler={workerMemoModalHandler}
      workerDeleteClickHandler={workerDeleteClickHandler}
      workerStopConfirmPopupHandler={workerStopConfirmPopupHandler}
      openCreateApiCodeModal={openCreateApiCodeModal}
      workerStopList={workerStopList}
      cancelWorkerStopId={cancelWorkerStopId}
      instanceType={instanceType}
      workerSettingValue={workerSettingValue}
    />
  );
}

export default DeployWorkerPage;
