import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import {
  DateRangePicker,
  InputText,
  Selectbox,
  Textarea,
} from '@jonathan/ui-react';

import dayjs from 'dayjs';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';
import MultiSelect from '@src/components/molecules/MultiSelect';
import ResourceSetting from '@src/components/molecules/ResourceSetting';

import { closeModal } from '@src/store/modules/modal';
import { callApi, STATUS_FAIL } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

import { executeWithLogging } from '@src/utils';

import classNames from 'classnames/bind';
import style from './WorkSpaceCheckModal.module.scss';

const cx = classNames.bind(style);

export const calConvertKorTime = (date) => {
  const newDate = dayjs(date, 'YYYY-MM-DD HH:mm')
    .add(9, 'hour')
    .format('YYYY-MM-DD HH:mm');
  return newDate;
};

// ! [계산] 스토리지 선택 값 찾는 함수
const calStorageList = (storageList, idValue) => {
  return storageList.find((info) => info.id === `${idValue}`);
};

// ! [계산] 선택된 스토리지 할당 값 함수
const calSelectValue = (storageList, idValue, sizeValue) => {
  return storageList.map((info) => {
    if (info.id === `${idValue}`) {
      return +sizeValue;
    } else {
      return '';
    }
  });
};

// ! [계산] User의 정보를 컴포넌트에 맞게 변경하는 함수
const calChangeUserValue = (userList) => {
  const copyList = userList.slice();
  const changeList = copyList.map((userInfo) => {
    return {
      label: userInfo.name,
      value: userInfo.id,
    };
  });
  return changeList;
};

// // ! [계산] 인스턴스 할당량 초과 체크 계산 함수
// const calCheckInstanceAllocate = (allocate_instance_list, instance_list) => {
//   if (!allocate_instance_list || !instance_list) return false;
//   let isCheck = false;

//   allocate_instance_list.forEach((allocateInfo) => {
//     const allocateInstanceInfo = instance_list.find((instanceInfo) => {
//       return instanceInfo.id === allocateInfo.instance_id;
//     });
//     if (allocateInfo.instance_allocate > allocateInstanceInfo.free)
//       isCheck = true;
//   });
//   return isCheck;
// };

// ! [계산] 스토리지 초과 체크 계산 함수
const calCheckStorageAllocate = (
  storage_list,
  data_storage_id,
  data_storage_size,
  main_storage_id,
  main_storage_size,
) => {
  if (!storage_list || !main_storage_id || !data_storage_id) return false;
  let isCheck = false;
  const mainStorage = storage_list.find(
    (storageInfo) => +storageInfo.id === main_storage_id,
  );
  const dataStorage = storage_list.find(
    (storageInfo) => +storageInfo.id === data_storage_id,
  );

  if (main_storage_id === data_storage_id) {
    const requestSize = main_storage_size + data_storage_size;
    if (requestSize > mainStorage.free_size) isCheck = true;
  }

  if (main_storage_id !== data_storage_id) {
    if (main_storage_size > mainStorage.free_size) isCheck = true;
    if (data_storage_size > dataStorage.free_size) isCheck = true;
  }
  return isCheck;
};

// ! [계산] 경고 메세지 반환 함수
const calMessage = (
  // isCheckInstanceAllocate,
  // isCheckStorageAllocate,
  serverFooterMessage,
  t,
) => {
  // console.log('isCheckInstanceAllocate : ', isCheckInstanceAllocate);
  // if (isCheckInstanceAllocate) return t('instance.allocate.error.message');
  // if (isCheckStorageAllocate) return t('storage.allocate.error.message');
  if (serverFooterMessage) return serverFooterMessage;
  return '';
};

// ! [계산] 모달의 submit 버튼 활성화 계산 함수
const calValidate = (calMessage) => {
  return !calMessage;
};

const initialInfo = {
  instance_list: [],
  request_workspace_info: {
    allocate_instance_list: [],
    cpu_core: null,
    create_datetime: '',
    data_storage_id: null,
    data_storage_size: null,
    description: '',
    end_datetime: '',
    id: null,
    main_storage_id: null,
    main_storage_size: null,
    manager_id: null,
    name: '',
    path: null,
    ram: null,
    start_datetime: null,
    user_list: null,
  },
  storage_list: [],
  user_group_list: [],
  user_list: [],
};

const WorkSpaceCheckModal = ({ data, type }) => {
  const { t } = useTranslation();
  const { workspaceId, getWorkSpaceFunc } = data;
  const dispatch = useDispatch();

  const [workspaceInfo, setWorkspaceInfo] = useState(initialInfo);
  const { instance_list, request_workspace_info, storage_list, user_list } =
    workspaceInfo;
  const {
    allocate_instance_list,
    create_datetime,
    start_datetime,
    end_datetime,
    manager_id,
    name,
    description,
    user_list: requestUserList,
    main_storage_id,
    data_storage_id,
    main_storage_size,
    data_storage_size,
  } = request_workspace_info;

  const transformStartDatetime = calConvertKorTime(start_datetime);
  const transformEndDatetime = calConvertKorTime(end_datetime);

  const [serverFooterMessage, setServerFooterMessage] = useState('');

  // ** 워크스페이스 매니저 **
  const workspaceManager = useMemo(() => {
    return user_list.find((userInfo) => userInfo.id === manager_id);
  }, [manager_id, user_list]);

  // ** 워크스페이스 매니저 선택 아이템 **
  const workspaceManagerSelectItem = useMemo(() => {
    return {
      label: workspaceManager ? workspaceManager.name : '',
      value: workspaceManager ? workspaceManager.id : '',
    };
  }, [workspaceManager]);

  // ** 워크스페이스 자원 설정 인스턴스 할당 리스트 **
  const filterInstanceList = useMemo(() => {
    return instance_list.filter((info) =>
      allocate_instance_list.some(({ instance_id }) => instance_id === info.id),
    );
  }, [instance_list, allocate_instance_list]);

  // ** 인스턴스 할당 체크 박스 값 **
  const instanceGpuOptions = useMemo(() => {
    return Array(filterInstanceList.length)
      .fill(null)
      .map((el, idx) => {
        return {
          [idx]: true,
        };
      });
  }, [filterInstanceList]);

  // ** 인스턴스 할당량 값 **
  const instanceInputValues = useMemo(() => {
    const copyShallowList = allocate_instance_list.slice();
    return copyShallowList.map((el) => el.instance_allocate);
  }, [allocate_instance_list]);

  // ** 선택된 메인 스토리지 값 **
  const selectMainStorage = useMemo(() => {
    const selectValue = calStorageList(storage_list, main_storage_id);
    return selectValue;
  }, [main_storage_id, storage_list]);

  // ** 선택된 데이터 스토리지 값 **
  const selectDataStorage = useMemo(() => {
    const selectValue = calStorageList(storage_list, data_storage_id);
    return selectValue;
  }, [data_storage_id, storage_list]);

  // ** 선택된 메인 스토리지 할당 값 **
  const mainSelectValue = useMemo(() => {
    const selectValue = calSelectValue(
      storage_list,
      main_storage_id,
      main_storage_size,
    );
    return selectValue;
  }, [storage_list, main_storage_id, main_storage_size]);

  // ** 선택된 데이터 스토리지 할당 값 **
  const dataSelectValue = useMemo(() => {
    const selectValue = calSelectValue(
      storage_list,
      data_storage_id,
      data_storage_size,
    );
    return selectValue;
  }, [storage_list, data_storage_id, data_storage_size]);

  // ** 유저 리스트 **
  const userList = useMemo(() => {
    const changeList = calChangeUserValue(user_list);
    return changeList;
  }, [user_list]);

  const selectUserList = useMemo(() => {
    const filterList = user_list.filter((userInfo) =>
      requestUserList.some((id) => userInfo.id === id),
    );
    const changeList = calChangeUserValue(filterList);
    return changeList;
  }, [user_list, requestUserList]);

  // // ** 인스턴스 할당량 초과 체크 값 **
  // const isCheckInstanceAllocate = calCheckInstanceAllocate(
  //   allocate_instance_list,
  //   instance_list,
  // );

  // ** 스토리지 할당량 초과 체크 값 **
  const isCheckStorageAllocate = calCheckStorageAllocate(
    storage_list,
    data_storage_id,
    data_storage_size,
    main_storage_id,
    main_storage_size,
  );

  const footerMessage = calMessage(
    // isCheckInstanceAllocate,
    // isCheckStorageAllocate,
    serverFooterMessage,
    t,
  );
  const validate = calValidate(footerMessage);

  const handleApprove = async (workspaceId, getWorkSpaceFunc) => {
    let isSuccess = '';
    await executeWithLogging(async () => {
      const res = await callApi({
        url: 'workspaces/request-accept',
        method: 'post',
        body: {
          request_workspace_id: workspaceId,
          manager_id,
          workspace_name: name,
          allocate_instances: allocate_instance_list,
          start_datetime: create_datetime,
          end_datetime,
          users_id: requestUserList,
          description,
          data_storage_id: data_storage_id,
          data_storage_request: data_storage_size,
          main_storage_id: main_storage_id,
          main_storage_request: main_storage_size,
        },
      });

      if (res.status === STATUS_FAIL) {
        isSuccess = false;
        setServerFooterMessage(res.message || res.error.message);
      } else {
        isSuccess = true;
        await getWorkSpaceFunc();
      }
    });
    return isSuccess;
  };

  const handleDecline = useCallback(async (workspaceId, getWorkSpaceFunc) => {
    executeWithLogging(async () => {
      await callApi({
        url: 'workspaces/request-refuse',
        method: 'delete',
        body: {
          request_workspace_id: workspaceId,
        },
      });
      await getWorkSpaceFunc();
    });
  }, []);

  // ** 초기 데이터 받아오는 Hook **
  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;

    const getWorkspaceOption = async (workspaceId) => {
      executeWithLogging(async () => {
        const { result } = await callApi({
          url: `workspaces/request-option?request_workspace_id=${workspaceId}`,
          method: 'get',
          signal,
        });
        setWorkspaceInfo(result);
      });
    };

    getWorkspaceOption(workspaceId);

    return () => controller.abort();
  }, [workspaceId]);

  return (
    <NewStyleModalFrame
      apply={{
        text: t('accept.label'),
        func: async () => {
          await handleApprove(workspaceId, getWorkSpaceFunc);
          return dispatch(closeModal(type));
        },
      }}
      cancel={{
        text: t('decline.label'),
        func: async () => {
          await handleDecline(workspaceId, getWorkSpaceFunc);
        },
      }}
      type={type}
      xCloseOnly
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={t('createWorkspace.label')}
      footerMessage={footerMessage}
      customStyle={{
        width: '664px',
      }}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('workspaceName.label')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            placeholder={t('workspaceName.placeholder')}
            name='workspace'
            value={name}
            isReadOnly
            isLowercase
            options={{ maxLength: 50 }}
            autoFocus={true}
            disableLeftIcon
            disableClearBtn
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('workspaceDescription.label')}
          optionalText={t('optional.label')}
          labelSize='large'
          optionalSize='medium'
          disableErrorMsg
        >
          <Textarea
            size='large'
            placeholder={t('workspaceDescription.placeholder')}
            value={description}
            name='description'
            isShowMaxLength
            isReadOnly
          />
        </InputBoxWithLabel>
      </div>
      <div className={cx('row')}>
        <ResourceSetting
          // ** 인스턴스 설정 [가져다 붙임] **
          isInstance
          models={filterInstanceList}
          gpuSelectedOptions={instanceGpuOptions}
          inputValue={instanceInputValues}
          checkboxHandler={() => {}}
          onChangeGpuInputValue={() => {}}
          edit={true}
          type={type}
          // ** Storage **
          isStorage
          list={storage_list}
          prevStorageModel={[]}
          storageSelectHandler={() => {}}
          mainStorageSelectedModel={selectMainStorage}
          dataStorageSelectedModel={selectDataStorage}
          storageInputValueHandler={() => {}}
          mainStorageValue={main_storage_size}
          dataStorageValue={data_storage_size}
          isReadOnly
          isMainStorageDisabled={true}
          isDataStorageDisabled={true}
          prevMainStorageVolume={main_storage_size}
          prevDataStorageVolume={data_storage_size}
        />
      </div>
      <div className={cx('column')}>
        <div className={cx('calendar')}>
          <label>{t('expiration.label')}</label>
          <DateRangePicker
            t={t}
            size='large'
            isReadOnly
            from={transformStartDatetime.split(' ')[0]}
            to={transformEndDatetime.split(' ')[0]}
            customStyle={{
              primaryType: {
                inputForm: {
                  display: 'flex',
                  justifyContent: 'space-evenly',
                  width: '100%',
                  color: '#121619',
                  borderRadius: '8px',
                },
                inputFont: {
                  fontSize: '14px',
                  fontWeight: 500,
                },
              },
            }}
          />
        </div>
        <InputBoxWithLabel
          labelText={t('workspaceManager.label')}
          labelSize='large'
        >
          <Selectbox
            type='search'
            size='medium'
            isReadOnly
            list={user_list.map(({ id, name }) => ({
              label: name,
              value: id,
            }))}
            placeholder={t('workspaceManager.placeholder')}
            name='manager'
            selectedItem={workspaceManagerSelectItem}
            customStyle={{
              fontStyle: {
                selectbox: {
                  color: '#121619',
                  textShadow: 'None',
                  fontSize: '14px',
                },
                list: {
                  fontSize: '14px',
                },
              },
            }}
          />
        </InputBoxWithLabel>
      </div>
      <MultiSelect
        label='users.label'
        listLabel='availableUsers.label'
        selectedLabel='chosenUsers.label'
        list={userList}
        selectedList={selectUserList}
        onChange={() => {}}
        readOnly={true}
      />
    </NewStyleModalFrame>
  );
};

export default WorkSpaceCheckModal;
