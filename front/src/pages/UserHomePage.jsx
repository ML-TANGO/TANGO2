import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import UserHomeContent from '@src/components/pageContents/user/UserHomeContent';

import { startPath } from '@src/store/modules/breadCrumb';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

function UserHomePage({ trackingEvent }) {
  const { t } = useTranslation();

  // Router Hooks
  const history = useHistory();
  const match = useRouteMatch();
  const { id: wid } = match.params;

  // Redux hooks
  const dispatch = useDispatch();

  // State
  const [trainingItems, setTrainingItems] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [historyItem, setHistoryItem] = useState([]);
  const [serverError, setServerError] = useState(false);
  const [isManager, setIsManager] = useState(false);
  const [storageData, setStorageData] = useState(null);
  const [gpuUsage, setGpuUsage] = useState([
    {
      used: '-',
      type: 'Training',
      total: '-',
    },
    {
      used: '-',
      type: 'Deployment',
      total: '-',
    },
  ]);
  const [workspaceResourceUsage, setWorkspaceResourceUsage] = useState({
    gpu: { total: 0, used: 0, usage: 0 },
    cpu: { total: 0, used: 0, usage: 0 },
    ram: { total: 0, used: 0, usage: 0 },
  });
  const [totalInstanceCondition, setTotalInstanceCondition] = useState([]);
  const [projectInstanceInfo, setProjectInstanceInfo] = useState([]);
  const [dailyResourceUsage, setDailyResourceUsage] = useState({
    gpu: null,
    cpu: null,
    ram: null,
    storage_data: null,
    storage_main: null,
    pricing: null,
  });
  const [mainStorageInfo, setMainStorageInfo] = useState({
    avail: 0,
    project_list: [],
    total: 0,
    usage: 0,
    used: 0,
  });

  const [dataStorageInfo, setDataStorageInfo] = useState({
    avail: 0,
    dataset_list: [],
    total: 0,
    usage: 0,
    used: 0,
  });

  const [info, setInfo] = useState({
    name: '-',
    description: '-',
    status: '-',
    users: [],
  });

  const [totalCount, setTotalCount] = useState([
    {
      variation: 0,
      total: '-',
      name: 'Docker Images',
    },
    {
      variation: 0,
      total: '-',
      name: 'Datasets',
    },
    {
      variation: 0,
      total: '-',
      name: 'Trainings',
    },
    {
      variation: 0,
      total: '-',
      name: 'Deployments',
    },
  ]); // totalCount

  const [originData, setOriginData] = useState([]);

  const getWorkspacesData = async () => {
    const response = await callApi({
      url: 'workspaces',
      method: 'GET',
    });
    const { status, result, message, error } = response;

    const combineArray = [...result.list];

    if (status === STATUS_SUCCESS) {
      setOriginData(combineArray);

      // 상세정보에서 넘어 올 경우
    } else {
      // errorToastMessage(error, message);
    }
  };

  /**
   * 워크스페이스 홈 데이터 가져오기
   *
   * @param {boolean} isFirst 처음 호출 여부
   * @param {boolean} isWUpdated 워크스페이스 변경 여부
   */
  const getHomeData = useCallback(
    async (isFirst) => {
      const response = await callApi({
        url: `dashboard/user?workspace_id=${wid}`,
        method: 'GET',
      });

      const { result, status, message, error } = response;

      if (status === STATUS_SUCCESS) {
        const {
          info,
          total_count: totalCount,
          usage,
          project_items: trainingItems,
          history,
          detailed_timeline,
          manager: isManager,
          instances_used,
          project_instance_allocate,
          storage,
        } = result;

        if (isFirst) setTimeline(detailed_timeline);
        setMainStorageInfo(storage.main_storage);
        setDataStorageInfo(storage.data_storage);
        setHistoryItem(history);
        setInfo(info);
        setWorkspaceResourceUsage(usage);
        setTotalInstanceCondition(instances_used);
        setProjectInstanceInfo(
          project_instance_allocate.map(({ instance_info, ...rest }) => ({
            ...rest,
            ...instance_info,
          })),
        );
        setTotalCount([
          {
            variation: 0,
            total: totalCount.images,
            name: 'Docker Images',
          },
          {
            variation: 0,
            total: totalCount.datasets,
            name: 'Datasets',
          },
          {
            variation: 0,
            total: totalCount.trainings,
            name: 'Trainings',
          },
          {
            variation: 0,
            total: totalCount.deployments,
            name: 'Deployments',
          },
        ]);
        if (usage) {
          setGpuUsage(usage.gpu);
        }
        setTrainingItems(trainingItems);
        setServerError(false);
        setIsManager(isManager);
      } else {
        // errorToastMessage(error, message);
        setServerError(true);
      }
      return true;
    },
    [wid],
  );

  const getResourceData = useCallback(async () => {
    const timelineResponse = await callApi({
      url: `dashboard/user/resource-usage?workspace_id=${wid}`,
      method: 'GET',
    });

    const { result, status } = timelineResponse;

    const { timeline } = result;
    if (status === STATUS_SUCCESS && timeline) {
      setDailyResourceUsage(timeline);
    }

    return true;
  }, [wid]);

  // storage 사용량 동기화
  const getStorageData = useCallback(async () => {
    const response = await callApi({
      url: `storage/${wid}/workspace`,
      method: 'PUT',
    });

    const { status, result, error, message } = response;

    if (status === STATUS_SUCCESS) {
      const newStorageData = {
        //! avail: result.workspace.workspace_avail,
        //! pcent: result.workspace.workspace_pcent,
        avail: 1, //TODO 임시
        pcent: 1, //TODO 임시
        share: result.share,
      };
      if (result.share === 0) {
        // 할당형
        newStorageData.size = result.workspace.workspace_size;
        newStorageData.used = result.workspace.workspace_used;
      } else {
        // 공유형
        newStorageData.used = result.used;
        newStorageData.size = result.size;
        //! newStorageData.workspaceUsed = result.workspace.workspace_used;
        newStorageData.workspaceUsed = 1;
        //TODO 임시
      }

      setStorageData(newStorageData);
      return true;
    } else {
      // errorToastMessage(error, message);
      setStorageData({
        used: 0,
        avail: 0,
        pcent: 0,
        size: 0,
        workspaceUsed: 0,
      });
      return false;
    }
  }, [wid]);

  /**
   * 페이지 바로가기
   *
   * @param {string} path (docker_images | datasets | trainings | deployments)
   */
  const directLink = (path) => {
    if (path === 'monthprice') return; // 월 평균 사용 요금 탭 누르면 early return 처리

    history.push(`/user/workspace/${wid}/${path}`);

    // Google Analytics
    let target = '';
    if (path === 'docker_images') {
      target = 'Docker Image';
    } else if (path === 'datasets') {
      target = 'Dataset';
    } else if (path === 'trainings') {
      target = 'Training';
    } else if (path === 'deployments') {
      target = 'Deployment';
    }
    if (target !== '') {
      trackingEvent({
        category: 'User Home Page',
        action: `Move To ${target} Page`,
      });
    }
  };

  /**
   * 최근 학습 현황에서 실제 JOB/HPS 목록으로 이동
   *
   * @param {number} trainingId 학습 ID
   * @param {string} trainingName 학습 이름
   * @param {string} itemType job or hps
   */
  const moveJobList = (trainingId, trainingName, itemType) => {
    history.push({
      pathname: `/user/workspace/${wid}/trainings/${trainingId}/workbench/${itemType}`,
      state: {
        id: trainingId,
        name: trainingName,
        loc: ['Home', trainingName, 'Workbench', itemType.toUpperCase()],
      },
    });
    trackingEvent({
      category: 'User Home Page',
      action: `Move To ${itemType.toUpperCase()} Page`,
    });
  };

  /**
   * 워크스페이스 설명 수정 모달 열기
   */
  const openWsDescEditModal = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_WORKSPACE',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              getWorkspacesData();
              getHomeData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceListData: originData,
          data: originData.filter((info) => info.id === Number(wid))[0],
        },
      }),
    );
  };

  /**
   * 워크스페이스 GPU 수정 모달 열기
   */
  const openGPUSettingEditModal = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_GPU_SETTING',
        modalData: {
          submit: {
            text: 'save.label',
            func: () => {
              dispatch(closeModal());
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceId: wid,
        },
      }),
    );
  };

  const breadCrumbHandler = useCallback(() => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Home',
            t,
          },
        },
      ]),
    );
  }, [dispatch, t]);

  useEffect(() => {
    breadCrumbHandler();
  }, [breadCrumbHandler, getHomeData]);

  useEffect(() => {
    loadModalComponent('EDIT_WORKSPACE_RESOURCE');
    loadModalComponent('EDIT_GPU_SETTING');
    getWorkspacesData();
    getHomeData();
  }, []);

  useIntervalCall(getHomeData, 1000);
  useIntervalCall(getResourceData, 60000);

  return (
    <UserHomeContent
      trainingItems={trainingItems}
      totalCount={totalCount}
      directLink={directLink}
      moveJobList={moveJobList}
      gpuUsage={gpuUsage}
      history={historyItem}
      timeline={timeline}
      info={info}
      openWsDescEditModal={openWsDescEditModal}
      openGPUSettingEditModal={openGPUSettingEditModal}
      serverError={serverError}
      isManager={isManager}
      storageData={storageData}
      workspaceResourceUsage={workspaceResourceUsage}
      totalInstanceCondition={totalInstanceCondition}
      projectInstanceInfo={projectInstanceInfo}
      dailyResourceUsage={dailyResourceUsage}
      mainStorageInfo={mainStorageInfo}
      dataStorageInfo={dataStorageInfo}
      workspaceId={wid}
    />
  );
}

export default UserHomePage;
