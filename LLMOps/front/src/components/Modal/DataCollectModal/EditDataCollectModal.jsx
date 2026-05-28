import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import AccessOwnerSelect from '@src/components/molecules/AccessOwnerSelect';
import MultiSelect from '@src/components/molecules/MultiSelect';

import { puCollect } from '@src/apis/flightbase/dataset/collect';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';
import CollectCycle from './CollectCycle';
import CollectLocation from './CollectLocation/CollectLocation';
import CollectMethodList from './CollectMethodList';
import CollectMethodRadio from './CollectMethodRadio/CollectMethodRadio';
import CollectResourceSetting from './CollectResourceSetting/CollectResourceSetting';
import CollectSizeLimit from './CollectSizeLimit';
import DescTextArea from './DescTextArea/DescTextArea';
import useCollectMethod from './hooks/useCollectMethod';
import useInstanceSetting from './hooks/useInstanceSetting';
import useLocation from './hooks/useLocation';
import NameInput from './NameInput/NameInput';
import useNameInput from './NameInput/useNameInput';
import PublicApiSelect from './PublicApiSelect';
import TooltipContent from './TooltipContent/TooltipContent';

import { calFooterMessage, getCollectOptions, getPublicApi } from './util';

export default function EditDataCollectModal({ data, type }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const { workspaceId, dataId, info, members, resetFunc } = data;
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const {
    name: editName,
    description: editDescribe,
    dataset_id: editDatasetId,
    dataset_name: editDatasetName,
    dataset_path: editDatasetPath,
    collect_cycle: editCollectCycle,
    collect_method,
    collect_cycle_unit,
    collect_storage_size,
    collect_storage_unit,
    access,
    owner: editOwner,
    instance_count,
    instance_id,
    collect_information_list: editCollectInfoList,
  } = info;

  // ** [수집 이름] **
  const labelText = t('collect.name.label');
  const placeholder = t('collect.name.placeholder');
  const { name, isValidateName, handleName } = useNameInput();

  // ** [수집 설명] **
  const [describe, setDescribe] = useState(editDescribe ?? '');
  const handleDescribe = useCallback((e) => {
    setDescribe(e.target.value);
  }, []);

  // ** [수집 자원 설정] **
  const {
    selectedInstance,
    instanceList,
    setInstanceList,
    handleSelectInstance,
    handleGpuValue,
  } = useInstanceSetting();

  // ** [수집 위치] **
  const {
    datasetValue,
    folderValue,
    datasetList,
    folderList,
    setDatasetList,
    handleSelectedLocation,
  } = useLocation(editDatasetId, editDatasetPath);

  // ** [공공 API 데이터 목록]
  const [publicDataList, setPublicDataList] = useState([]);

  // ** [수집 방법] **
  const {
    collectMethod,
    collectMethodTitle,
    collectMethodColumn,
    collectMethodList,
    collect_information_list,
    selectedApiList,
    setDeploymentList,
    handleMethod,
    handleMethodModal,
    handlePublicApiSelect,
  } = useCollectMethod(
    collect_method,
    editCollectInfoList,
    workspaceId,
    publicDataList,
  );

  // ** [수집 주기] **
  const [collectCycle, setCollectCycle] = useState({
    value: editCollectCycle,
    unit: collect_cycle_unit,
  });
  const { value: cycleValue, unit: cycleUnit } = collectCycle;
  const handleCollectCycle = useCallback(({ name, value }) => {
    setCollectCycle((prev) => ({
      ...prev,
      [name]: value,
    }));
  }, []);

  // ** [수집 용량 제한] **
  const [sizeLimit, setSizeLimit] = useState(collect_storage_unit ? 1 : 0);
  const handleSizeLimit = useCallback((e) => {
    setSizeLimit(+e.target.value);
  }, []);

  const [sizeLimitValue, setSizeLimitValue] = useState({
    value: collect_storage_size,
    unit: collect_storage_unit,
  });
  const { value: limitSizeValue, unit: limitSizeUnit } = sizeLimitValue;
  const handleSizeLimitValue = useCallback((name, value) => {
    setSizeLimitValue((prev) => ({
      ...prev,
      [name]: value,
    }));
  }, []);

  // ** [접근 권한] **
  const [isAccess, setIsAccess] = useState(access);
  const handleIsAccess = useCallback((e) => {
    setIsAccess(+e.target.value);
  }, []);

  // ** [소유자] **
  const tooltipContent = useMemo(() => {
    return <TooltipContent />;
  }, []);
  const [owner, setOwner] = useState(editOwner);
  const [ownerList, setOwnerList] = useState([]);
  const handleOwner = useCallback((value) => {
    setOwner(value);
  }, []);

  // ** 사용자[선택 항목] **
  const userList = useRef([]);
  const handleSelectedUserList = useCallback((selectedList) => {
    const copyList = selectedList.slice();
    const transformList = copyList.map((item) => item.value);
    userList.current = transformList;
  }, []);

  const submit = {
    text: t('update.label'),
    func: async () => {
      const body = {
        name,
        workspace_id: +workspaceId,
        description: describe,
        dataset_id: datasetValue.id,
        dataset_path: folderValue.id,
        instance_id: selectedInstance.instance_id,
        instance_count: selectedInstance.front.value,
        collect_method: collectMethod,
        collect_cycle: cycleValue,
        collect_cycle_unit: cycleUnit,
        collect_storage_limit: Boolean(sizeLimit),
        collect_storage_size: limitSizeValue,
        collect_storage_unit: limitSizeUnit,
        collect_information_list,
        access: +isAccess,
        owner_id: owner.id,
        members: isAccess ? [] : userList.current,
      };
      const { status, message } = await puCollect(dataId, body);
      if (status === STATUS_SUCCESS) {
        await resetFunc();
        dispatch(closeModal(type));
      } else {
        toast.error(message);
      }
    },
  };

  const footerMessage = calFooterMessage(
    name,
    false,
    selectedInstance,
    datasetValue,
    folderValue,
    collectCycle,
    sizeLimit,
    sizeLimitValue,
    collectMethod,
    collect_information_list,
  );
  const isValidate = !footerMessage;

  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => {
    getCollectOptions(
      workspaceId,
      userName,
      members,
      isLoading,
      setIsLoading,
      setOwnerList,
      setOwner,
      setInstanceList,
      setDatasetList,
      setDeploymentList,
    );
    getPublicApi(setPublicDataList);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    members,
    setDatasetList,
    setDeploymentList,
    setInstanceList,
    userName,
    workspaceId,
  ]);

  useEffect(() => {
    if (!dataId) return;

    handleName(editName);
  }, [dataId, editName, handleName]);

  useEffect(() => {
    if (ownerList.length === 0) return;
    const findOwnerValue = ownerList.find((info) => info.name === editOwner);
    setOwner(findOwnerValue);
  }, [editOwner, ownerList]);

  const isFetching = useRef(false);
  useEffect(() => {
    if (instanceList.length === 0) return;
    if (isFetching.current) return;

    isFetching.current = true;
    handleGpuValue(instance_count, +instance_id);
  }, [handleGpuValue, instanceList.length, instance_count, instance_id]);

  return (
    <NewStyleModalFrame
      title={'수집 수정'}
      type={type}
      submit={submit}
      cancel={{
        text: t('cancel.label'),
      }}
      isResize={true}
      isMinimize={true}
      validate={isValidate}
      footerMessage={footerMessage}
    >
      <NameInput
        value={name}
        labelText={labelText}
        placeholder={placeholder}
        isError={false}
        handleName={() => {}}
        isReadOnly={true}
      />
      <DescTextArea value={describe} handleDescribe={handleDescribe} />
      <CollectResourceSetting
        isFetching={isLoading}
        listData={instanceList}
        handleSelectInstance={handleSelectInstance}
        handleGpuValue={handleGpuValue}
      />
      <CollectLocation
        isFetching={isLoading}
        type='edit'
        datasetValue={{ name: editDatasetName, value: editDatasetId }}
        folderValue={{ name: editDatasetPath }}
        datasetList={datasetList}
        folderList={folderList}
        handleSelectedLocation={handleSelectedLocation}
      />
      <CollectMethodRadio value={collectMethod} handleMethod={handleMethod} />
      {collectMethod === 'public_api' && (
        <PublicApiSelect
          options={publicDataList}
          valueList={selectedApiList}
          handleSelected={handlePublicApiSelect}
        />
      )}
      <CollectMethodList
        title={collectMethodTitle}
        collectMethodColumn={collectMethodColumn}
        collectMethodList={collectMethodList}
        handleMethodModal={handleMethodModal}
      />
      <CollectCycle
        cycleValue={cycleValue}
        cycleUnit={cycleUnit}
        handleCollectCycle={handleCollectCycle}
      />
      <CollectSizeLimit
        value={sizeLimit}
        limitSizeValue={limitSizeValue}
        limitSizeUnit={limitSizeUnit}
        handleSizeLimit={handleSizeLimit}
        handleSizeLimitValue={handleSizeLimitValue}
      />
      <AccessOwnerSelect
        isAccess={isAccess}
        tooltipContents={tooltipContent}
        handleInputs={handleIsAccess}
        ownerValue={owner?.value}
        ownerList={ownerList}
        handleOwner={handleOwner}
      />
      {isAccess === 0 && (
        <MultiSelect
          label='users.label'
          listLabel='availableUsers.label'
          selectedLabel='chosenUsers.label'
          list={ownerList} // 초기 목록
          selectedList={members} // 초기 선택된 목록
          onChange={({ selectedList }) => handleSelectedUserList(selectedList)} // 변경 이벤트
          exceptItem={owner && owner.value} // 목록에서 빠질 아이템
          optional
          style={{ marginTop: '32px' }}
        />
      )}
    </NewStyleModalFrame>
  );
}
