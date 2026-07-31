import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { toast } from 'react-toastify';

import PlaygroundDropdown from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundDropdown';

import { collectOptions } from '@src/apis/flightbase/dataset/collect';
import { closeModal } from '@src/store/modules/modal';
import { STATUS_SUCCESS } from '@src/network';

import { DeleteButton } from '../AddWebcrowler/AddWebcrowler';
import { visiblityList } from '../DataCollectModal/CollectLocation/CollectLocation';
import NewStyleModalFrame from '../NewStyleModalFrame';

const calFooterMessage = (selectedProject) => {
  if (!selectedProject.id) return '배포 프로젝트를 선택해 주세요.';
  return;
};

const calFilterProjectList = (projectList, selectedVisible, userName) => {
  if (projectList.length === 0) return [];
  if (selectedVisible.value === 0) return projectList;

  const filterList = projectList.filter((info) => {
    return info.user_name === userName;
  });
  return filterList;
};

const getOptionsList = async (
  workspaceId,
  isFetching,
  setProjectList,
  setIsFetching,
) => {
  if (!isFetching) return;
  const { status, message, result } = await collectOptions(workspaceId);
  if (status === STATUS_SUCCESS) {
    const transformList = result.deployment_list.map((info) => ({
      ...info,
      backname: info.user_name,
    }));
    setProjectList(transformList);
  } else {
    toast.error(message);
  }
  setIsFetching(false);
};

// ** 삭제 버튼 핸들러 **
export const handleFlightbaseDeleteButton = (
  name,
  owner,
  setCollectMethodList,
) => {
  setCollectMethodList((prev) => {
    const shallowList = prev['flightbase'].slice();
    const findIndex = shallowList.findIndex(
      ({ first, second }) => first === name && second === owner,
    );
    shallowList.splice(findIndex, 1);
    return {
      ...prev,
      flightbase: shallowList,
    };
  });
};

export default function AddDeployProjectModal({ type, data }) {
  const { t } = useTranslation();
  const { workspaceId, collectMethodList, setCollectMethodList } = data;
  const { flightbase: FbList } = collectMethodList;

  const dispatch = useDispatch();
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [selectedVisible, setSelectedVisible] = useState(visiblityList[0]);
  const handleSelectedVisible = useCallback((v) => {
    setSelectedVisible(v);
  }, []);

  const [isFetching, setIsFetching] = useState(true);
  const [projectList, setProjectList] = useState([]);
  const filterList = calFilterProjectList(
    projectList,
    selectedVisible,
    userName,
  );

  const calDisabledList = (FbList, filterList) => {
    if (!filterList.length) return [];
    if (!FbList.length) return filterList;

    const result = filterList.map((item) => ({
      ...item,
      disabled: FbList.some((bItem) => bItem.first === item.name), // b 배열에 동일한 name이 있으면 disabled 추가
    }));
    return result;
  };
  const disabledList = calDisabledList(FbList, filterList);

  const [selectedProject, setSelectedProject] = useState({
    id: null,
    name: null,
  });
  const handleSelected = useCallback((v) => {
    setSelectedProject(v);
  }, []);

  const footerMessage = calFooterMessage(selectedProject);

  const cancel = {
    text: t('cancel.label'),
  };

  const submit = {
    text: t('add.label'),
    func: () => {
      setCollectMethodList((prev) => {
        const shallowCopyList = prev.flightbase.slice();
        shallowCopyList.push({
          first: selectedProject.name,
          second: selectedProject.user_name,
          fourth: (
            <DeleteButton
              handleDeleteButton={() => {
                handleFlightbaseDeleteButton(
                  selectedProject.name,
                  selectedProject.user_name,
                  setCollectMethodList,
                );
              }}
            />
          ),
          id: selectedProject.id,
        });
        return {
          ...prev,
          flightbase: shallowCopyList,
        };
      });
      dispatch(closeModal(type));
    },
  };

  useEffect(() => {
    getOptionsList(workspaceId, isFetching, setProjectList, setIsFetching);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  return (
    <NewStyleModalFrame
      title={'배포 프로젝트 추가'}
      type={type}
      submit={submit}
      cancel={cancel}
      validate={!footerMessage}
      footerMessage={footerMessage}
      customStyle={{ width: '568px' }}
    >
      <PlaygroundDropdown
        isFetching={isFetching}
        label='프로젝트'
        value={selectedProject}
        placeholder='사용하실 프로젝트를 선택하세요.'
        options={disabledList}
        handleSelected={handleSelected}
        visibilityValue={selectedVisible}
        visiblityList={visiblityList}
        handleVisibility={handleSelectedVisible}
        icon={'/src/static/images/icon/icon-deployments-black.svg'}
      />
    </NewStyleModalFrame>
  );
}
