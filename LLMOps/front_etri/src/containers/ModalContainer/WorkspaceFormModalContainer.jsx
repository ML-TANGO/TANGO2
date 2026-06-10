// Utils
import { PureComponent } from 'react';
import { withTranslation } from 'react-i18next';

import {
  convertLocalTimeObj,
  convertUTCTime,
  convertUTCStartOfDay,
  convertUTCEndOfDay,
} from '@src/datetimeUtils';
import dayjs from 'dayjs';
import { uniqBy } from 'lodash';

// Components
import WorkspaceFormModal from '@src/components/Modal/WorkspaceFormModal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

import {
  convertBinaryByte,
  convertSizeTo,
  convertSizeToBinaryBytes,
  errorReturnMessage,
  errorToastMessage,
} from '@src/utils';

class WorkspaceFormModalContainer extends PureComponent {
  constructor(props) {
    super(props);
    const now = new Date();

    // 기간(Period of Use)의 초기 값
    const startdatetime = dayjs(); // 시작 날짜 (현재 시간으로 설정)
    const enddatetime = dayjs(
      new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0),
    ) // 종료 날짜 (현재 시간 기준 해당 날짜의 11:59:59)
      .add(31, 'days')
      .subtract(1, 'seconds');
    const minDate = dayjs();

    this.state = {
      userInit: true,
      validate: false, // 모달의 submit 버튼 활성/비활성 여부 상태 값
      workspaceId: '', // Workspace id 값
      workspace: '', // Workspace Name 값
      workspaceError: null, // Workspace Name input 에러 텍스트
      startdatetime, // 기간 시작 날짜 값
      prevStartdatetime: startdatetime, // 현재 저장된 시작 날짜
      enddatetime, // 기간 종료 날짜 값
      minDate, //최소 날짜 값
      modalNoticeMessage: null,
      periodError: '', // 기간 에러 텍스트
      guarantee: true, // gpu 보장 여부
      trainingGpu: '', // Training GPU
      trainingGpuError: null, // Training GPU input 에러 텍스트
      deploymentGpu: '', // Service GPU
      deploymentGpuError: null, // Service GPU input 에러 텍스트
      manager: '', // Workspace 관리자 이름
      managerList: [], // Workspace 관리자 목록
      // new
      gpuModels: [], // new key gpu models
      instanceList: [],
      mainStorageValue: 0,
      dataStorageValue: 0,
      gpuInputValues: [],
      gpuSelectedOptions: [],

      gpuTrainInputValue: [],
      gpuDeployInputValue: [],
      prevGpuSelectedOptions: [],

      cpuModels: [],
      cpuSelectedOptions: [],
      cpuInputValues: [],
      storageSelectedOption: [],
      storageInputValues: [],

      managerError: null, // Workspace 관리자 input 에러 텍스트
      selectedManager: null, // 선택된 Workspace 관리자
      userList: [], // 초기 유저 목록
      groupList: [], // 사용자 그룹 목록
      userGroupOptions: [],
      selectedList: [], // 초기 선택된 유저 목록
      tmpSelectedList: [], // 선택된 Users 값 생성 수정시 파라미터로 쓰임
      description: '', // Workspace 설명
      descriptionError: null, // Workspace 설명 에러
      gpuCount: 0,
      gpuTotal: 0,
      gpuFreeMap: {},

      datasetStorageSelected: [],
      datasetStorageValue: [],

      projectStorageSelected: [],
      projectStorageValue: [],

      storageList: [],

      storageInputValue: '',
      storageInputValueByte: 0,
      storageError: null,
      storageMessage: null,
      mainStorageSelectedModel: null,
      dataStorageSelectedModel: null,
      editStorageAvailableSize: 0,
      createStorageAvailableSize: 0,
      prevStorageModel: [],
      storageBarData: {},
      workspaceListData: [],
      workspaceUsage: 0,

      footerMessage: 'test',
      serverMessage: '',
      prevWorkspaceInfo: [],
      workspaceNameValidMessage: '',
      totalStorageInputValue: 0,
      prevMainStorageVolume: 0,
      prevDataStorageVolume: 0,
    };
  }

  _isMounted = false;

  _isRequestGpuInfo = {};

  async componentDidMount() {
    this._isMounted = true;
    // 유저 목록 조회

    const {
      type,
      data: { data: workspaceData, workspaceListData },
    } = this.props;

    const {
      userList: users,
      groupList: groups,
      storageList,
      gpuModels,
      workspaceInfo,
      instanceList,
    } = await this.getUsersData();

    if (type === 'EDIT_WORKSPACE') {
      const response = await callApi({
        url: `workspaces/option?workspace_id=${workspaceData.id}`,
        method: 'get',
      });
      const { result, status } = response;

      if (status === STATUS_SUCCESS) {
        const workspaceName = workspaceData?.name;

        const {
          end_datetime: enddatetime,
          start_datetime: startdatetime,
          id: workspaceId,
          description,
        } = workspaceData;

        const {
          // workspace_name: workspace,
          // start_datetime: startdatetime,
          // end_datetime: enddatetime,
          gpu_training_total: trainingGpu,
          gpu_deployment_total: deploymentGpu,
          allocated_models: allocatedModels,
          // workspace_info: workspaceInfo,
          // manager_id: managerId,
          // user: selectedUsers,

          guaranteed_gpu: guarantee,
        } = result;

        const userList = [];
        const selectedList = [];
        const managerId = workspaceInfo?.manager_id;

        const selectedUsers = workspaceInfo?.users;

        // const { instance_list: instanceList } = workspaceInfo;

        for (let i = 0; i < users.length; i += 1) {
          const userItem = users[i];
          const { id: userId } = userItem;
          let flag = false;
          for (let j = 0; j < selectedUsers.length; j += 1) {
            const { id: selectedUserId } = selectedUsers[j];
            if (userId === selectedUserId) {
              flag = true;
              break;
            }
          }
          if (flag) {
            selectedList.push(userItem);
          } else {
            userList.push(userItem);
          }
        }

        const prevStorageData = [];
        let workspaceUsage = 0;

        // eslint-disable-next-line no-unused-vars
        let prevUsed = '';

        const storageId = workspaceData.usage?.storage_id;

        workspaceListData.forEach((list) => {
          if (list.name === workspaceName) {
            if (list.usage) {
              workspaceUsage = Number(list.usage.size);
            }
          }
        });

        storageList.forEach((list) => {
          if (list.id === storageId) {
            prevStorageData.push(list);
            // default min capacity - 공유형
            let minCapacity = convertBinaryByte(list.usage?.used);
            let otherStorageSize =
              prevStorageData[0]?.usage.allocate_used - workspaceUsage;

            if (list.share === 0) {
              minCapacity = convertSizeTo(workspaceData?.usage?.size, 'GiB');
              if (otherStorageSize !== 0) {
                if (
                  isNaN(
                    Number(
                      convertBinaryByte(otherStorageSize).split(' GiB')[0],
                    ),
                  )
                ) {
                  otherStorageSize = Math.ceil(
                    Number(
                      convertBinaryByte(otherStorageSize).split(' TiB')[0],
                    ),
                  );
                } else {
                  otherStorageSize = Math.ceil(
                    Number(
                      convertBinaryByte(otherStorageSize).split(' GiB')[0],
                    ),
                  );
                }
              }
            }

            if (isNaN(Math.ceil(Number(minCapacity.split(' GiB')[0])))) {
              prevUsed = Math.ceil(Number(minCapacity.split(' TiB')[0]));
            } else {
              prevUsed = Math.ceil(Number(minCapacity.split(' GiB')[0]));
            }
          }
        });

        const resultUserList = userList.map(
          ({ name: userName, id: userId }) => ({
            label: userName,
            value: userId,
          }),
        );

        let manager = {};

        if (Array.isArray(users)) {
          const { id: value, name: label } = users.filter(
            ({ id }) => id === parseInt(managerId, 10),
          )[0];
          manager = { label, value };
        }
        // gpu 사용 가능 수 조회

        const sDateTime = convertLocalTimeObj(startdatetime);
        const eDateTime = convertLocalTimeObj(enddatetime);

        const { gpuCount, gpuTotal } = await this.getGpuInfo(
          sDateTime,
          eDateTime,
          guarantee,
        );

        if (workspaceInfo && workspaceInfo.instance_list.length > 0) {
          async function selectInstances() {
            for (let i = 0; i < workspaceInfo.instance_list.length; i += 1) {
              const instanceName = workspaceInfo.instance_list[i].instance_name;
              const allocateValue =
                workspaceInfo.instance_list[i].instance_allocate;

              const index = instanceList.findIndex(
                (aElement) => aElement.name === instanceName,
              );

              if (index !== -1) {
                await checkboxHandlerAsync({ idx: index });
                await onChangeGpuInputValueAsync({
                  idx: index,
                  value: allocateValue,
                });
              }
            }
          }

          const checkboxHandlerAsync = ({ idx, flag }) => {
            return new Promise((resolve) => {
              this.checkboxHandler({ idx, flag }, resolve);
            });
          };

          const onChangeGpuInputValueAsync = ({ idx, value }) => {
            return new Promise((resolve) => {
              this.onChangeGpuInputValue({ idx, value }, resolve);
            });
          };

          selectInstances();
        }

        if (type === 'EDIT_WORKSPACE') {
          const selectedMainStorage = storageList.find(
            (info) => +info.id === workspaceInfo.main_storage_id,
          );
          const selectedDataStorage = storageList.find(
            (info) => +info.id === workspaceInfo.data_storage_id,
          );
          this.setState({
            mainStorageSelectedModel: selectedMainStorage,
            dataStorageSelectedModel: selectedDataStorage,
          });
        }

        this.setState({
          workspaceId,
          workspace: workspaceName,
          workspaceError: '',
          startdatetime: sDateTime,
          prevStartdatetime: sDateTime,
          enddatetime: eDateTime,
          minDate: sDateTime.isAfter(dayjs()) ? dayjs() : sDateTime,
          trainingGpu,
          trainingGpuError: '',
          deploymentGpu,
          deploymentGpuError: '',
          manager,
          managerError: '',
          userList: resultUserList,
          groupList: groups,
          userGroupOptions: [...groups, ...resultUserList],
          selectedList: selectedList.map(({ name: userName, id: userId }) => ({
            label: userName,
            value: userId,
          })),
          selectedListError: '',
          gpuCount,
          gpuTotal,
          storageList,
          description: !description ? '' : description,
          descriptionError: description ? '' : null,
          guarantee: guarantee === 1,
          storageError: '',
          //! editStorageAvailableSize: maxInputValue,
          // storageInputValue: prevUsed,
          storageInputValue: '',
          workspaceUsage: workspaceUsage,
          prevStorageModel: prevStorageData,
          prevWorkspaceInfo: workspaceInfo,
          // mainStorageValue: [selectedMainStorage.],
          //!
          // storageBarData: {
          //   ...this.state.storageBarData,
          //   otherUsage: {
          //     pcent: otherStorageUsagePcent,
          //     usage: otherStorageUsage,
          //   },
          //   currUsage: {
          //     pcent: (workspaceUsage / storageSize) * 100,
          //     usage: workspaceUsage,
          //   },
          //   // remaining: remainingSize,
          // },
          //!
        });
      }
    } else {
      // gpu 사용 가능 수 조회
      const newState = {};
      const { gpuCount, gpuTotal } = await this.getGpuInfo();

      if (storageList && storageList.length > 0) {
        const storageInputValue = storageList.map((v) => {
          return 0;
        });
        newState.dataStorageValue = storageInputValue;
        newState.mainStorageValue = storageInputValue;
      }

      this.setState({
        ...newState,
        gpuCount,
        gpuTotal,
        storageList,
        userGroupOptions: [
          ...groups,
          ...users.map(({ name: userName, id: userId }) => ({
            label: userName,
            value: userId,
          })),
        ],
        storageError: !storageList ? '' : null,
      });
    }
  }

  componentDidUpdate() {
    const {
      workspace,
      manager,
      gpuSelectedOptions,
      gpuInputValues,
      mainStorageSelectedModel,
      mainStorageValue,
      dataStorageSelectedModel,
      dataStorageValue,
      workspaceNameValidMessage,
    } = this.state;
    const { type } = this.props;
    const transKey =
      workspaceNameValidMessage === '이미 사용중인 workspace 이름입니다.'
        ? 'useWorkspace.desc'
        : 'readyWorkspace.desc';

    const validations = [
      {
        condition:
          workspaceNameValidMessage === '이미 사용중인 workspace 이름입니다.' ||
          workspaceNameValidMessage === '요청 대기중인 workspace 이름입니다.',
        message: `${this.props.t(transKey)}`,
      },
      {
        condition: !workspace,
        message: `${this.props.t('workspaceName.empty.message')}`,
      },
      {
        condition:
          gpuSelectedOptions.length > 0 &&
          !this.checkGpuInputValues(gpuSelectedOptions, gpuInputValues),
        message: `${this.props.t('trainingInstance.error.message')}`,
      },
      {
        condition: this.calGpuAllocateZero(gpuInputValues, gpuSelectedOptions),
        message: `${this.props.t('instance.allocate.message')}`,
      },
      {
        condition:
          type === 'CREATE_WORKSPACE' &&
          (!mainStorageSelectedModel ||
            mainStorageValue[mainStorageSelectedModel.idx] === '' ||
            mainStorageValue[mainStorageSelectedModel.idx] === 0),
        message: `${this.props.t('mainStorageSelect.error.message')}`,
      },
      {
        condition:
          type === 'CREATE_WORKSPACE' &&
          (!dataStorageSelectedModel ||
            dataStorageValue[dataStorageSelectedModel.idx] === '' ||
            dataStorageValue[dataStorageSelectedModel.idx] === 0),
        message: `${this.props.t('dataStorageSelect.error.message')}`,
      },
      {
        condition: !manager.label,
        message: `${this.props.t('workspaceManager.empty.message')}`,
      },
    ];

    for (const { condition, message } of validations) {
      if (condition) {
        this.setState({ footerMessage: message });
        return;
      }
    }

    if (this.state.serverMessage) {
      this.setState({ footerMessage: this.state.serverMessage });
      return;
    }

    this.setState({ footerMessage: '' });
  }

  componentWillUnmount() {
    this._isMounted = false;
  }

  gpuGetHandler = (list = []) => {
    const newState = {};
    // gpu 기본 state 깔기
    if (list?.length > 0) {
      let selectedOptions = [];

      let selectedItemValue = [];
      const initialInputValues = [];

      list.forEach((v, idx) => {
        selectedItemValue = [];
        selectedOptions.push({ [idx]: false });
        initialInputValues.push('');
      });

      newState.gpuSelectedOptions = selectedOptions;
      newState.gpuInputValues = initialInputValues;
    }
    this.setState(newState);
  };

  // GPU 모델 선택 이벤트 핸들러
  selectGpuModelHandler = (type, idx, nodeIdx) => {
    const { gpuModelListOptions, gpuUsage, gpuUsageError, cpuModelList } =
      this.state;

    let { gpuModelList } = this.state;
    let cpuModelListOptions = gpuModelListOptions[idx].node_list;
    let newState = {};

    // if (type === 'gpu') {
    gpuModelListOptions[idx].selected = !gpuModelListOptions[idx].selected;
    // GPU 모델 선택/선택해제시 CPU 모델 전체 선택/선택해제
    // cpuModelListOptions = cpuModelListOptions.map((v) => {
    //   return {
    //     ...v,
    //     selected: gpuModelListOptions[idx].selected,
    //   };
    // });
    // gpuModelListOptions[idx].node_list = cpuModelListOptions;
    // } else {
    //   // type === 'cpu'
    //   cpuModelListOptions[nodeIdx].selected =
    //     !cpuModelListOptions[nodeIdx].selected;
    //   gpuModelListOptions[idx].node_list = cpuModelListOptions;
    //   if (!gpuModelListOptions[idx].selected) {
    //     // GPU 선택 안되어 있을 경우 선택
    //     gpuModelListOptions[idx].selected = true;
    //   }
    //   if (!cpuModelListOptions[nodeIdx].selected) {
    //     // CPU 선택 해제하는 경우 CPU 선택 개수 0이면 GPU 선택도 해제
    //     if (
    //       cpuModelListOptions.filter(({ selected }) => selected).length === 0
    //     ) {
    //       gpuModelListOptions[idx].selected = false;
    //     }
    //   }
    // }
    cpuModelList[idx] = cpuModelListOptions.filter(({ selected }) => selected);
    gpuModelList = gpuModelListOptions.filter(({ selected }) => selected);

    newState = {
      cpuModelList,
      ...this.gpuModelState(
        gpuModelListOptions,
        gpuModelList,
        gpuUsage,
        gpuUsageError,
      ),
    };

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // Storage 목록 조회
  getStorageData = async () => {
    const url = 'storage';
    const response = await callApi({
      url,
      method: 'get',
    });
    const { status, result, error, message } = response;

    if (status === STATUS_SUCCESS) {
      return result;
    } else {
      errorToastMessage(error, message);
      return { list: null };
    }
  };

  onChangeGpuInputValue = ({ idx, value }, callback) => {
    // 그리고 여기도 동일하게 idx와 allocate를 value에 넣는다.

    const { state } = this;

    const { gpuInputValues } = state;
    const newState = {};

    const newGpuInputValue = [...gpuInputValues];

    newGpuInputValue[idx] = value;

    newState.gpuInputValues = newGpuInputValue;

    this.checkboxHandler({ idx, flag: !!value });

    this.setState(newState, () => {
      this.submitBtnCheck();
      if (callback) {
        callback();
      }
    });
  };

  /** ================================================================================
   * API START
   ================================================================================ */
  // 유저 목록 조회
  getUsersData = async () => {
    const {
      type,
      data: { data: workspaceData, workspaceListData },
    } = this.props;

    let url = 'workspaces/option';

    if (type === 'EDIT_WORKSPACE') {
      url = `workspaces/option?workspace_id=${workspaceData.id}`;
    }

    const response = await callApi({
      url,
      method: 'get',
    });
    const { status, result } = response;

    if (!this._isMounted) return { userList: [], groupList: [] };
    if (status === STATUS_SUCCESS) {
      const {
        user_list: userList,
        user_group_list: groupList,
        storage_list: storageList,
        gpu_models: gpuModels,
        allocated_models: allocatedModels,
        workspace_info: workspaceInfo,
        // cpu_models: cpuModels,
        instance_list: instanceList,
      } = result;

      if (workspaceInfo) {
        this.setState({
          mainStorageValue: workspaceInfo.main_storage_size,
          dataStorageValue: workspaceInfo.data_storage_size,
          prevDataStorageVolume: workspaceInfo.data_storage_size,
          prevMainStorageVolume: workspaceInfo.main_storage_size,
        });
      }

      const parseGroupList = groupList.map(
        ({ name: label, id: value, user_list: memberList }) => {
          return {
            label,
            value,
            memberList: memberList.map(({ name, id }) => ({
              label: name,
              value: id,
            })),
          };
        },
      );
      this.setState({
        userList: userList.map(({ name: userName, id: userId }) => ({
          label: userName,
          value: userId,
        })),
        instanceList: [...instanceList],
        // cpuModels: [...cpuModels],
        groupList: parseGroupList,
        managerList: [...userList],
      });
      this.gpuGetHandler(instanceList);

      return {
        userList,
        groupList: parseGroupList,
        storageList: storageList,
        gpuModels,
        allocatedModels,
        workspaceInfo,
        instanceList,
      };
    }
    return { userList: [], groupList: [] };
  };

  // 생성 가능한 gpu수 조회
  getGpuInfo = async (sdate, edate, currentGuarantee) => {
    const {
      type,
      data: { data: workspaceData },
    } = this.props;

    return 0;
  };

  instanceSubmitHandler = () => {
    const { state } = this;

    const { gpuSelectedOptions, gpuInputValues, instanceList } = state;

    const instance = [];

    gpuSelectedOptions.forEach((v, i) => {
      const value = Object.values(v)[0];

      if (
        value === true &&
        gpuInputValues[i] > 0 &&
        typeof gpuInputValues[i] === 'number'
      ) {
        instance.push({
          // resource_name: instanceList[i].name,
          instance_id: instanceList[i].id,

          instance_allocate: gpuInputValues[i],
        });
      }
    });

    return [instance];
  };

  getGpuFreeInCalendar = async (sdate, edate) => {
    const {
      type,
      data: { data: workspaceData },
    } = this.props;
    const { guarantee } = this.state;
    // const reqKey = `${sdate.format('YYYY-MM-DD')}_${edate.format(
    //   'YYYY-MM-DD',
    // )}`;
    // if (this._isRequestGpuInfo[reqKey]) return {};

    // this._isRequestGpuInfo[reqKey] = true;

    // let url = `gpu/workspace_aval_gpu_timeline?guaranteed_gpu=${
    //   guarantee ? 1 : 0
    // }&start_datetime=${convertUTCTime(
    //   sdate,
    //   'YYYY-MM-DD HH:mm',
    // )}&end_datetime=${convertUTCTime(edate, 'YYYY-MM-DD HH:mm')}`;

    // if (type === 'EDIT_WORKSPACE') {
    //   url = `${url}&workspace_id=${workspaceData.id}`;
    // }

    // const response = await callApi({
    //   url,
    //   method: 'get',
    // });

    // const { result, status, message, error } = response;

    // if (status === STATUS_SUCCESS) {
    //   return result;
    // }
    // this._isRequestGpuInfo[reqKey] = false;
    // errorToastMessage(error, message);
    return {};
  };

  // 모달의 Submit 버튼 클릭 시 실행되는 함수 (워크스페이스 생성 또는 수정)
  onSubmit = async (callback) => {
    const { data, type } = this.props;
    const { isAdmin } = data;

    let url = 'workspaces';
    let method = 'POST';
    const {
      workspaceId,
      workspace,
      trainingGpu,
      startdatetime,
      enddatetime,
      deploymentGpu,
      manager,
      tmpSelectedList: selectedList,
      description,
      guarantee,
      storageSelectedModel,
      mainStorageSelectedModel,
      mainStorageValue,
      dataStorageSelectedModel,
      dataStorageValue,
      storageInputValueByte,
      prevStorageModel,
      prevWorkspaceInfo,
    } = this.state;

    let body;

    const [instance] = this.instanceSubmitHandler();

    if (!isAdmin) {
      url = url + '/request';
    }

    if (type === 'CREATE_WORKSPACE') {
      body = {
        request_type: 'create',
        workspace_name: workspace,
        allocate_instances: instance,
        start_datetime: convertUTCStartOfDay(startdatetime),
        end_datetime: convertUTCEndOfDay(enddatetime),
        manager_id: manager.value,
        users_id: selectedList
          .map(({ value }) => value)
          .filter((value) => value !== manager.value),
        description,
        guaranteed_gpu: guarantee ? 1 : 0,
        data_storage_id: `${dataStorageSelectedModel?.id}`,
        data_storage_request:
          dataStorageValue ?? prevWorkspaceInfo?.data_storage_size,
        main_storage_request:
          mainStorageValue ?? prevWorkspaceInfo?.main_storage_size,
        main_storage_id: `${mainStorageSelectedModel?.id}`,
      };
      if (storageSelectedModel?.share === 0) {
        body.workspace_size = storageInputValueByte;
      }
    } else if (type === 'EDIT_WORKSPACE') {
      body = {
        request_type: 'update',
        workspace_id: workspaceId,
        workspace_name: workspace,
        allocate_instances: instance,
        // training_gpu: parseInt(trainingGpu, 10),
        // deployment_gpu: parseInt(deploymentGpu, 10),
        start_datetime: convertUTCStartOfDay(startdatetime),
        end_datetime: convertUTCEndOfDay(enddatetime),
        manager_id: manager.value,
        users_id: selectedList
          .map(({ value }) => value)
          .filter((value) => value !== manager.value),
        description,
        guaranteed_gpu: guarantee ? 1 : 0,
        data_storage_request:
          dataStorageValue ?? prevWorkspaceInfo?.data_storage_size,
        main_storage_request:
          mainStorageValue ?? prevWorkspaceInfo?.main_storage_size,
        data_storage_id: `${dataStorageSelectedModel?.id}`,
        main_storage_id: `${mainStorageSelectedModel?.id}`,
        // dataset_storages: [{}],
        // project_storage: {},
      };
      if (prevStorageModel[0]?.share === 0) {
        body.workspace_size = storageInputValueByte;
      }
    }

    if (type === 'EDIT_WORKSPACE' && isAdmin) method = 'put';
    if (type === 'EDIT_WORKSPACE' && !isAdmin) method = 'post';

    const response = await callApi({ url, method, body });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (callback) callback();
      console.log('success create workspace');

      return true;
    } else {
      errorToastMessage(error, message);
    }

    const errorMsg = errorReturnMessage(error, message);
    this.setState({ serverMessage: errorMsg });
    return false;
  };

  /** ================================================================================
   * API END
   ================================================================================ */

  /** ================================================================================
   * Event handler START
   ================================================================================ */

  // 텍스트 인풋 이벤트 핸들러
  inputHandler = async (e) => {
    const { name, value } = e.target;

    if (name === 'workspace') {
      const { workspaceNameValidMessage } = this.state;
      const { result, message } = await callApi({
        url: `workspaces/check/${value}`,
        method: 'get',
      });
      if (
        message === '이미 사용중인 workspace 이름입니다.' ||
        message === '요청 대기중인 workspace 이름입니다.'
      ) {
        this.setState({
          workspaceNameValidMessage: message,
        });
      } else {
        this.setState({
          workspaceNameValidMessage: 'OK',
        });
      }
    }

    const newState = {
      [name]: value,
      [`${name}Error`]: null,
    };

    const validate = this.validate(name, value);

    if (validate) {
      newState[`${name}Error`] = validate;
    } else if (name === 'description' && value.trim() === '') {
      newState[`${name}Error`] = null;
    } else {
      newState[`${name}Error`] = '';
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 넘버 인풋 이벤트 핸들러
  numberInputHandler = async (data) => {
    const { name, value } = data;
    const { gpuCount } = this.state;

    const newState = {
      [name]: value,
      [`${name}Error`]: null,
    };
    const cnt = parseInt(newState[name], 10);

    if ((name === 'trainingGpu' || name === 'deploymentGpu') && value !== '') {
      if (gpuCount < cnt) {
        newState[name] = gpuCount;
      } else if (cnt < 0) {
        newState[name] = 0;
      }
    }

    const validate = this.validate(
      name,
      (name === 'trainingGpu' || name === 'deploymentGpu') && value !== ''
        ? cnt
        : value,
    );

    if (validate) {
      newState[`${name}Error`] = validate;
    } else {
      newState[`${name}Error`] = '';
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  checkboxHandler = ({ idx, flag }, callback) => {
    const { gpuSelectedOptions, gpuUsage, gpuInputValues } = this.state;
    const {
      data: { workspaceListData },
      type,
    } = this.props;

    let newFlag = !Object.values(gpuSelectedOptions[idx])[0];

    if (typeof flag === 'boolean') {
      newFlag = flag;
    }

    let prevSelectedOptions = gpuSelectedOptions.slice(0, idx);
    let currSelectedOptions = {
      [idx]: newFlag,
    };
    let nextSelectedOptions = gpuSelectedOptions.slice(
      idx + 1,
      gpuSelectedOptions.length,
    );

    const newState = {};

    // 체크해제시 해당 input값 초기화
    if (!newFlag) {
      const newGpuInputValues = [...gpuInputValues];
      newGpuInputValues[idx] = '';
      newState.gpuInputValues = newGpuInputValues;
    } else {
      // const newGpuValues = [...gpuInputValues].map((inputVal, index) => '');
      // newState.gpuInputValues = newGpuValues;
    }

    const newSelectedOptions = [
      ...prevSelectedOptions,
      currSelectedOptions,
      ...nextSelectedOptions,
    ];

    if (gpuUsage !== 0) {
      newState.gpuUsageError = '';
    }
    newState.gpuSelectedOptions = newSelectedOptions;

    this.setState(newState, () => {
      this.submitBtnCheck();
      if (callback) {
        callback();
      }
    });
  };

  // storage select 핸들러
  storageSelectHandler = ({ storage, idx, storageType }) => {
    const {
      data: { workspaceListData },
      type,
    } = this.props;

    const {
      storageInputValue,
      storageInputValueByte,
      storageError,
      storageMessage,
    } = this.state;

    const newState = {
      storageBarData: {
        otherUsage: { pcent: null, usage: null },
        currUsage: { pcent: null, usage: null },
      },
    };

    if (storageInputValue !== '') {
      newState.storageInputValue = '';
    }
    if (storageInputValueByte !== 0) {
      newState.storageInputValueByte = 0;
    }
    if (storageError === null) {
      newState.storageError = '';
    }
    if (storageMessage !== null) {
      newState.storageMessage = null;
    }

    if (storageType === 'main') {
      newState.mainStorageValue = 0;
      newState.mainStorageSelectedModel = {
        ...storage,
        idx,
      };
    } else {
      // data
      newState.dataStorageValue = 0;
      newState.dataStorageSelectedModel = {
        ...storage,
        idx,
      };
    }

    newState.storageSelectedModel = {
      ...storage,
      idx,
    };

    if (storage.share === 0) {
      // * 할당형이면
      const id = storage.id;
      let size = 0;

      workspaceListData.forEach((v) => {
        if (v.usage) {
          if (v.usage.storage_id === id) {
            size = size + v.usage.size;
          }
        }
      });

      if (type === 'CREATE_WORKSPACE' && storage.share === 0) {
        newState.storageBarData.currUsage.pcent = storageInputValue === '' && 0;
        newState.storageBarData.currUsage.usage =
          storageInputValue === '' && '0';

        const storageSizeGib = Number(
          convertSizeTo(storage.size, 'GiB')?.split(' GiB')[0],
        );
        const otherUsage = convertSizeTo(storage.usage.allocate_used, 'GiB');
        const otherPcent =
          (Number(
            convertSizeTo(storage.usage.allocate_used, 'GiB')?.split(' GiB')[0],
          ) /
            storageSizeGib) *
          100;
        newState.storageBarData.otherUsage.pcent = otherPcent;
        newState.storageBarData.otherUsage.usage = otherUsage;
        newState.createStorageAvailableSize = Math.floor(
          storageSizeGib - Number(otherUsage.split(' GiB')[0]) + 1,
        );
      }
    }
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  storageInputValueHandler = ({ value, type, id }) => {
    if (type === 'main') {
      // console.log(this);
      const selectedMainStorage = this.state.storageList.find(
        (info) => info.id === id,
      );
      this.setState({
        mainStorageValue: value,
        mainStorageSelectedModel: selectedMainStorage,
      });
    } else {
      const selectedDataStorage = this.state.storageList.find(
        (info) => info.id === id,
      );
      this.setState({
        dataStorageValue: value,
        dataStorageSelectedModel: selectedDataStorage,
      });
    }
  };

  // 스위치 버튼 이벤트 핸들러
  switchHandler = async () => {
    const { startdatetime, enddatetime, guarantee } = this.state;
    const { gpuCount, gpuTotal } = await this.getGpuInfo(
      startdatetime,
      enddatetime,
      !guarantee,
    );

    this.setState({
      gpuCount,
      gpuTotal,
      trainingGpu: '',
      trainingGpuError: null,
      deploymentGpu: '',
      deploymentGpuError: null,
      guarantee: !guarantee,
    });

    this.getGpuFreeInCalendar(startdatetime, enddatetime);
  };

  // 달력 인풋 핸들러
  calendarHandler = async (from, to) => {
    const f = dayjs(from);
    const t = dayjs(to);
    const { gpuCount } = await this.getGpuInfo(f, t);
    this.setState(
      {
        startdatetime: f,
        enddatetime: t,
        gpuCount,
        trainingGpu: '',
        deploymentGpu: '',
      },
      () => {
        this.submitBtnCheck();
      },
    );
  };

  // 달력 변경 감지
  calenderDetector = async (leftD, rightD, isHandle) => {
    if (isHandle) return;
    const { gpuFreeMap: prevGpuFreeMap } = this.state;
    const gpuFreeMap = { ...prevGpuFreeMap };
    let res1 = {};
    let res2 = {};
    if (leftD) {
      const s = dayjs(leftD).startOf('year');
      const e = dayjs(leftD).endOf('year');
      res1 = await this.getGpuFreeInCalendar(s, e);
    }
    if (rightD) {
      const s = dayjs(rightD).startOf('year');
      const e = dayjs(rightD).endOf('year');
      res2 = await this.getGpuFreeInCalendar(s, e);
    }
    const keys1 = Object.keys(res1);
    for (let i = 0; i < keys1.length; i += 1) {
      gpuFreeMap[keys1[i]] = res1[keys1[i]];
    }
    const keys2 = Object.keys(res2);
    for (let i = 0; i < keys2.length; i += 1) {
      gpuFreeMap[keys2[i]] = res2[keys2[i]];
    }

    if (!this._isMounted) return;
    this.setState({ gpuFreeMap });
  };

  // 달력 마운트 감지
  calenderMountDetector = () => {
    this._isRequestGpuInfo = {};
    this.calenderDetector(
      this.state.startdatetime.format('YYYY-MM-DD'),
      this.state.enddatetime.format('YYYY-MM-DD'),
    );
  };

  // 셀렉트 박스 인풋 핸들러
  selectManager = (selectedManager) => {
    const newState = {
      manager: selectedManager,
    };
    if (selectedManager) newState.managerError = '';
    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  // 할당용량 input handler
  storageInputHandler = (usage, size) => {
    const { prevStorageModel, storageSelectedModel, workspace } = this.state;
    const {
      type,
      data: { workspaceListData },
    } = this.props;

    const newState = {};

    let byteUsage = convertSizeToBinaryBytes(usage, 'GiB');

    let defaultUsage = 10;
    let minCapacity = convertSizeToBinaryBytes(10, 'GiB');
    let workspaceUsage = 0;

    if (type === 'EDIT_WORKSPACE') {
      minCapacity = convertBinaryByte(prevStorageModel[0]?.usage.used);

      if (prevStorageModel[0]?.share === 0) {
        minCapacity = convertBinaryByte(
          prevStorageModel[0]?.usage.allocate_used,
        );
      }
      if (minCapacity.indexOf(' GiB') !== -1) {
        minCapacity = Math.ceil(Number(minCapacity.split(' GiB')[0]));
        workspaceListData.forEach((list) => {
          if (list.name === workspace) {
            workspaceUsage = Number(list.usage.size);
          }
        });

        const currUsage = Math.ceil(
          Number(convertBinaryByte(workspaceUsage).split(' GiB')[0]),
        );

        defaultUsage = currUsage;
      } else if (minCapacity.indexOf(' TB') !== -1) {
        minCapacity = Math.ceil(Number(minCapacity.split(' TiB')[0]));
      }
    }

    if (type === 'CREATE_WORKSPACE') {
      byteUsage = byteUsage + storageSelectedModel.usage.allocate_used;
    } else {
      workspaceListData.forEach((list) => {
        if (list.name === workspace) {
          workspaceUsage = Number(list.usage.size);
        }
      });
      byteUsage =
        byteUsage + prevStorageModel[0].usage.allocate_used - workspaceUsage;
    }

    let avaliableSize = 9999;
    if (type === 'EDIT_WORKSPACE') {
      let currUsage = Number(
        convertSizeTo(workspaceUsage, 'GiB').split(' GiB')[0],
      );
      const totalOtherSize =
        prevStorageModel[0].usage.allocate_used / Math.pow(1024, 3);

      const nonWorkspace = totalOtherSize - currUsage;
      let availableUsage = Number(
        convertSizeTo(prevStorageModel[0]?.size, 'GiB')?.split(' GiB')[0],
      );
      avaliableSize = Math.floor(availableUsage - (nonWorkspace + currUsage));
    }

    if (usage > avaliableSize && type === 'EDIT_WORKSPACE') {
      newState.storageError = null;
      newState.storageMessage = 'enterMaxCapacity.message';

      const maxSize = Math.floor(size / Math.pow(1024, 3));
      let otherSize = 0;
      otherSize = prevStorageModel[0].usage.allocate_used / Math.pow(1024, 3);
      let currUsage = Number(
        convertSizeTo(workspaceUsage, 'GiB').split(' GiB')[0],
      );
      otherSize = otherSize - currUsage;
      const maxInputValue = Math.floor(maxSize - otherSize - currUsage) + 1;

      newState.storageInputValue = maxInputValue;
    } else if (byteUsage > size) {
      newState.storageError = null;
      newState.storageMessage = 'enterMaxCapacity.message';

      const maxSize = Math.floor(size / Math.pow(1024, 3));
      let otherSize = 0;
      if (type === 'CREATE_WORKSPACE') {
        otherSize = Math.floor(
          storageSelectedModel.usage.allocate_used / Math.pow(1024, 3),
        );
      } else {
        otherSize = prevStorageModel[0].usage.allocate_used / Math.pow(1024, 3);
      }

      newState.storageInputValue = maxSize;
      if (type === 'CREATE_WORKSPACE') {
        newState.storageInputValue = maxSize - otherSize + 1;
      } else {
        let currUsage = Number(
          convertSizeTo(workspaceUsage, 'GiB').split(' GiB')[0],
        );
        otherSize = otherSize - currUsage;
        const maxInputValue = Math.floor(maxSize - otherSize - currUsage) + 1;
        newState.storageInputValue = maxInputValue;
      }
    } else if (usage < defaultUsage && type === 'CREATE_WORKSPACE') {
      newState.storageMessage = 'enterMinCapacity.message';
      newState.storageError = null;
      newState.storageInputValue = usage;
    } else if (minCapacity > size) {
      newState.storageMessage = 'noStorageCapacity.message';
      newState.storageError = null;
    } else {
      newState.storageInputValueByte = usage + 'G';
      newState.storageMessage = 'storageCapacityValid.message';
      newState.storageError = '';
      newState.storageInputValue = usage;
    }

    this.setState(newState, () => {
      this.submitBtnCheck();
    });
  };

  multiSelectHandler = ({ selectedList }) => {
    const tmpSelectedList = [];
    for (let i = 0; i < selectedList.length; i += 1) {
      const item = selectedList[i];
      const { memberList } = item;
      if (memberList) {
        for (let j = 0; j < memberList.length; j += 1) {
          const member = memberList[j];
          tmpSelectedList.push(member);
        }
      } else {
        tmpSelectedList.push(item);
      }
    }

    this.setState({ tmpSelectedList: uniqBy(tmpSelectedList, 'value') }, () => {
      this.submitBtnCheck();
    });
  };

  // 유효성 검증 함수
  validate = (name, value) => {
    if (name === 'workspace') {
      const forbiddenChars = /[\\<>:*?"'|:;`{}^$ &[\]!\uAC00-\uD7A3ㄱ-ㅎㅏ-ㅣ]/;
      const regType = !forbiddenChars.test(value);

      if (value === '') {
        return 'workspaceName.empty.message';
      }
      if (!regType) {
        return 'newNameRule.message';
      }
    } else if (name === 'period') {
      if (value === 1) {
        return 'startDate.error.message';
      }
      if (value === 2) {
        return 'endDate.error.message';
      }
    } else if (name === 'trainingGpu') {
      const { gpuCount, deploymentGpu } = this.state;
      if (value === '') {
        return 'trainingGpuCount.empty.message';
      }
      if (gpuCount - deploymentGpu < value && gpuCount - deploymentGpu > 0) {
        return 'trainingGpuCount.error.message';
      }
    } else if (name === 'deploymentGpu') {
      const { gpuCount, trainingGpu } = this.state;
      if (value === '') {
        return 'deploymentGpuCount.empty.message';
      }
      if (gpuCount - trainingGpu < value && gpuCount - trainingGpu > 0) {
        return 'deploymentGpuCount.error.message';
      }
    } else if (name === 'manager') {
      if (value === '') {
        return 'workspaceManager.empty.message';
      }
    }
    return null;
  };

  checkGpuInputValues(gpuCheckValue, inputValue) {
    for (let i = 0; i < gpuCheckValue.length; i++) {
      const value = Object.values(gpuCheckValue[i])[0];

      if (
        value === true &&
        inputValue[i] >= 0 &&
        typeof inputValue[i] === 'number'
      ) {
        return true;
      }
    }
    return false;
  }

  calGpuAllocateZero = (gpuInputValues, gpuSelectedOptions) => {
    let isValidate = false;
    gpuSelectedOptions.forEach((isCheck, idx) => {
      if (isCheck[idx]) {
        if (!gpuInputValues[idx]) isValidate = true;
      }
    });
    return isValidate;
  };

  // submit 버튼 활성 여부 체크 함수
  submitBtnCheck = () => {
    // submit 버튼 활성/비활성
    const { state } = this;
    const {
      cpuSelectedOptions,
      cpuInputValues,
      gpuSelectedOptions,
      gpuInputValues,
      mainStorageSelectedModel,
      mainStorageValue,
      datasetStorageSelected,
      dataStorageSelectedModel,
      dataStorageValue,
      workspaceNameValidMessage,
    } = state;

    const { type } = this.props;
    const stateKeys = Object.keys(state);

    let validateCount = 0;

    for (let i = 0; i < stateKeys.length; i += 1) {
      const key = stateKeys[i];

      if (key !== 'descriptionError' && key.indexOf('Error') !== -1) {
        if (state[key] !== '') {
          if (
            key !== 'trainingGpuError' &&
            key !== 'deploymentGpuError' &&
            key !== 'storageError'
          ) {
            validateCount += 1;
          }
        }
      }
    }
    if (
      workspaceNameValidMessage === '이미 사용중인 workspace 이름입니다.' ||
      workspaceNameValidMessage === '요청 대기중인 workspace 이름입니다.'
    ) {
      validateCount += 1;
    }

    // ** 인스턴스가 체크 박스가 체크되어 있는데 할당량이 0일 때**
    const isGpuAllocateZero = this.calGpuAllocateZero(
      gpuInputValues,
      gpuSelectedOptions,
    );
    if (isGpuAllocateZero) validateCount += 1;

    if (gpuSelectedOptions.length > 0) {
      const gpuValidate = this.checkGpuInputValues(
        gpuSelectedOptions,
        gpuInputValues,
      );
      if (!gpuValidate) {
        validateCount += 1;
      }
    }

    if (type !== 'EDIT_WORKSPACE') {
      if (mainStorageSelectedModel) {
        const index = mainStorageSelectedModel?.idx;
        if (mainStorageValue[index] === '' || mainStorageValue[index] === 0) {
          validateCount += 1;
        }
      } else {
        validateCount += 1;
      }

      if (dataStorageSelectedModel) {
        const index = dataStorageSelectedModel?.idx;
        if (dataStorageValue[index] === '' || dataStorageValue[index] === 0) {
          validateCount += 1;
        }
      } else {
        validateCount += 1;
      }
    }

    // if (
    //   storageSelectedModel &&
    //   type === 'CREATE_WORKSPACE' &&
    //   storageInputValueByte === 0 &&
    //   storageSelectedModel &&
    //   storageSelectedModel.share === 0
    // ) {
    //   validateCount += 1;
    // }

    // true가 있는지 검사
    // 해당 true에 값이 0 이상인지 체크

    // train에 하나이상 deploy에 하나 이상이 위 사항 충족하는지 체크

    const validateState = { validate: false };
    if (validateCount === 0) {
      validateState.validate = true;
    }

    this.setState(validateState);
  };

  /** ================================================================================
   * Event handler END
   ================================================================================ */

  render() {
    const {
      state,
      props,
      inputHandler,
      numberInputHandler,
      switchHandler,
      calendarHandler,
      calenderDetector,
      calenderMountDetector,
      selectManager,
      multiSelectHandler,
      storageSelectHandler,
      storageInputHandler,
      onSubmit,
      checkboxHandler,
      onChangeGpuInputValue,
      storageInputValueHandler,
    } = this;

    return (
      <WorkspaceFormModal
        {...state}
        {...props}
        inputHandler={inputHandler}
        numberInputHandler={numberInputHandler}
        switchHandler={switchHandler}
        calendarHandler={calendarHandler}
        calenderDetector={calenderDetector}
        calenderMountDetector={calenderMountDetector}
        selectManager={selectManager}
        multiSelectHandler={multiSelectHandler}
        storageSelectHandler={storageSelectHandler}
        onSubmit={onSubmit}
        storageInputHandler={storageInputHandler}
        checkboxHandler={checkboxHandler}
        onChangeGpuInputValue={onChangeGpuInputValue}
        storageInputValueHandler={storageInputValueHandler}
        isAdmin={!!this.props.data.isAdmin}
      />
    );
  }
}

export default withTranslation()(WorkspaceFormModalContainer);
