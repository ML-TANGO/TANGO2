import { toast } from 'react-toastify';

import {
  collectOptions,
  getCollectPublicData,
} from '@src/apis/flightbase/dataset/collect';
import { STATUS_SUCCESS } from '@src/network';

export const calFooterMessage = (
  name,
  isNameError,
  selectedInstance,
  datasetValue,
  folderValue,
  collectCycle,
  sizeLimit,
  sizeLimitValue,
  collectMethod,
  collect_information_list,
) => {
  if (!name) return '이름을 입력해 주세요.';
  if (isNameError)
    return '이름을 확인해주세요 (제외문자 :한글, !?*<>#^$%&(){}[]_`\':;/"|\\ 및 공백)';
  if (!selectedInstance) return '수집 자원을 설정해 주세요.';
  if (!selectedInstance.front.value) return '인스턴스 할당해 주세요.';
  if (!datasetValue.id) return '사용하실 데이터셋을 선택해 주세요.';
  if (!folderValue.id) return '사용하실 폴더를 선택해 주세요.';

  if (collect_information_list.length === 0) {
    if (collectMethod === 'public_api') return 'API 데이터를 추가해 주세요.';
    if (collectMethod === 'crawling') return '웹 크롤러를 추가해 주세요.';
    if (collectMethod === 'remote_server') return '원격 서버를 추가해 주세요.';
    return '배포 프로젝트를 등록해 주세요.';
  }

  if (!collectCycle.value) return '수집 주기를 입력해 주세요.';
  if (!collectCycle.unit) return '수집 주기 단위를 선택해 주세요.';
  if (sizeLimit) {
    if (!sizeLimitValue.value) return '수집 용량을 입력해 주세요.';
    if (!sizeLimitValue.unit) return '수집 용량 단위를 선택해 주세요.';
  }
  return '';
};

export const getCollectOptions = async (
  workspaceId,
  userName,
  members,
  isFetching,
  setIsFetching,
  setOwnerList,
  setOwner,
  setInstanceList,
  setDatasetList,
  setDeploymentList,
) => {
  if (!isFetching) return;
  const { result, status, message } = await collectOptions(workspaceId);
  setIsFetching(false);

  if (status === STATUS_SUCCESS) {
    const { dataset_list, instance_list, user_list, deployment_list } = result;

    const transfromInstanceList = instance_list.map((info) => ({
      ...info,
      front: {
        isCheck: false,
        value: 0,
      },
    }));
    const transformDatasetList = dataset_list.map((info) => ({
      ...info,
      name: info.dataset_name,
    }));
    const transformUserName = user_list.map((info) => ({
      ...info,
      label: info.name,
      value: info.id,
    }));
    const findSelectName = transformUserName.find(
      (info) => info.label === userName,
    );
    const filterList = transformUserName.filter((item1) => {
      return !members.some((item2) => item2.value === item1.value);
    });

    setOwnerList(filterList);
    setOwner(findSelectName);
    setInstanceList(transfromInstanceList);
    setDatasetList(transformDatasetList);
    setDeploymentList(deployment_list);
  } else {
    toast.error(message);
  }
};

export const getPublicApi = async (setPublicList) => {
  const { result, status, message } = await getCollectPublicData();

  if (status === STATUS_SUCCESS) {
    setPublicList(result);
  } else {
    toast.error(message);
  }
};
