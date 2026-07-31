import { useCallback, useEffect, useState } from 'react';
//i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import UserDeploymentContent from '@src/components/pageContents/user/UserDeploymentContent';
import NewDeploymentWizard from '@src/components/Modal/NewDeploymentWizard';

import { startPath } from '@src/store/modules/breadCrumb';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';
// network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

// Utils
import {
  errorToastMessage,
  scrollToPrevPosition,
  sortDescending,
} from '@src/utils';

// import Hangul from '@src/koreaUtils';

/**
 * 유저 배포 목록 페이지
 * @component
 * @example
 *
 * return (
 *  <UserDeploymentPage />
 * );
 *
 *
 * -
 */
function UserDeploymentPage() {
  // 컴포넌트 상태
  const [isLoading, setIsLoading] = useState(true); // 배포 목록 조회 로딩 여부 (boolean)
  const [deploymentList, setDeploymentList] = useState([]); // 배포 목록 값 (Array)
  const [selectedFilter, setSelectedFilter] = useState([]); // 체크된 필터 목록 (Array<{ label: string, value: string }>)
  const [keywordFilter, setKeywordFilter] = useState(''); // 검색 필터 (string)
  const [isWizardOpen, setIsWizardOpen] = useState(false); // wizard 모달 노출 여부 (boolean)

  const { t } = useTranslation();

  // Redux Hooks
  const dispatch = useDispatch();

  // Router Hooks
  const match = useRouteMatch();
  const { id: workspaceId } = match.params; // 브라우저 url의 path 파라미터의 워크스페이스 id 값
  const history = useHistory();

  /**
   * 그룹 list 조회
   */
  // const getGroupData = useCallback(async () => {
  //   const response = await callApi({
  //     url: `deployments/template-group-list?workspace_id=${workspaceId}`,
  //     method: 'GET',
  //   });
  //   const { result } = response;
  //   result.deployment_template_group_info_list?.forEach((data, index) => {
  //     if (data.description) {
  //       result.deployment_template_group_info_list[index].descriptionAssemble =
  //         Hangul.make(data.description);
  //     }
  //   });
  //   setGroupData(result.deployment_template_group_info_list);
  //   setDefaultGroupName(result.deployment_template_group_new_name);
  // }, [workspaceId]);

  // const getTemplateData = useCallback(
  //   async (id = clickedGroupId) => {
  //     let url = `deployments/template-list?workspace_id=${workspaceId}`;
  //     if (id !== null) url += `&deployment_template_group_id=${id}`;
  //     if (noGroupSelectedStatus) url += `&is_ungrouped_template=1`;
  //     const response = await callApi({
  //       url,
  //       method: 'GET',
  //     });
  //     const { result } = response;
  //     setTemplateData(
  //       result?.deployment_template_info_list
  //         ? result.deployment_template_info_list
  //         : [],
  //     );
  //     setDefaultTemplateName(() => result.deployment_template_new_name);
  //   },
  //   [clickedGroupId, noGroupSelectedStatus, workspaceId],
  // );

  // const onClickNoGroup = () => {
  //   setNoGroupSelectedStatus((prev) => !prev);
  //   setClickedGroupId(null);
  //   setSelectedGroupData(null);
  // };

  // const onClickGroupList = (data) => {

  //   setNoGroupSelectedStatus(false);
  //   if (data.id === clickedGroupId) {
  //     setClickedGroupId(null);
  //     setSelectedGroupData(null);
  //   } else {
  //     setSelectedGroupData(data);
  //     setClickedGroupId(data.id);
  //   }
  // };

  /**
   * 배포 목록 조회
   */
  const getDeploymentList = useCallback(async () => {
    const response = await callApi({
      url: `deployments?workspace_id=${workspaceId}`,
      method: 'GET',
    });

    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      const resultList = Array.isArray(result)
        ? result.map((d) => {
            return { ...d };
          })
        : [];
      const sortList = sortDescending(resultList.reverse(), 'bookmark');
      setDeploymentList(sortList);
      setIsLoading(false);
      return true;
    }
    errorToastMessage(error, message);
    return false;
  }, [workspaceId]);

  useIntervalCall(getDeploymentList, 1000, () => {
    const path = sessionStorage.getItem(`deployment/${workspaceId}_scroll_pos`);
    if (history.action === 'POP' && path) {
      const path = `deployment/${workspaceId}`;
      scrollToPrevPosition(path);
    } else {
      sessionStorage.removeItem(`deployment/${workspaceId}_scroll_pos`);
    }
  });

  // 배포 목록 필터링
  const listFilter = () => {
    // 빌트인 모델 명, 배포 소유자 명, 배포 이름
    return deploymentList.filter(
      ({
        deployment_type: type,
        built_in_model_name: builtInModelName = '',
        user_name: user = '',
        deployment_name: deploymentName = '',
        deployment_status: { status },
        permission_level: permissionLevel,
      }) => {
        // 검색 필터
        let searchFlag = false;
        if (keywordFilter !== '') {
          if (
            (builtInModelName &&
              builtInModelName
                .toLowerCase()
                .indexOf(keywordFilter.toLowerCase()) !== -1) ||
            (user &&
              user.toLowerCase().indexOf(keywordFilter.toLowerCase()) !== -1) ||
            (deploymentName &&
              deploymentName
                .toLowerCase()
                .indexOf(keywordFilter.toLowerCase()) !== -1)
          ) {
            searchFlag = true;
          }
        } else {
          searchFlag = true;
        }

        // 조건 필터
        let activatedFilterFlag = true;
        let deActivatedFilterFlag = true;
        let builtInFilterFlag = true;
        let customFilterFlag = true;
        let accessibleFilterFlag = true;
        for (let i = 0; i < selectedFilter.length; i += 1) {
          const { value } = selectedFilter[i];
          if (value === 'ACTIVATED') {
            // 자원 사용
            if (status !== 'running') activatedFilterFlag = false;
          } else if (value === 'DEACTIVATED') {
            // 자원 미사용
            if (status === 'running') deActivatedFilterFlag = false;
          } else if (value === 'BUILT_IN') {
            // 빌트인 타입
            if (type !== 'built-in') builtInFilterFlag = false;
          } else if (value === 'CUSTOM') {
            // 커스텀 타입
            if (type !== 'custom') customFilterFlag = false;
          } else if (value === 'ACCESSIBLE') {
            // 접근 가능
            if (permissionLevel > 4) accessibleFilterFlag = false;
          } else if (value === 'INACCESSIBLE') {
            // 접근 불가능
            if (permissionLevel < 5) accessibleFilterFlag = false;
          }
        }

        return (
          searchFlag &&
          activatedFilterFlag &&
          deActivatedFilterFlag &&
          customFilterFlag &&
          builtInFilterFlag &&
          accessibleFilterFlag
        );
      },
    );
  };

  // Events
  /**
   * 필터나 뷰타입이 변경 될 경우 실행되는 함수
   */
  const watchFilterViewType = useCallback(
    ({ filter, search }) => {
      if (filter) setSelectedFilter(filter);
      if (search !== undefined) setKeywordFilter(search);
    },
    [setSelectedFilter],
  );

  /**
   * 배포 생성 모달 열기
   */
  const openCreateDeploymentModal = () => {
    setIsWizardOpen(true);
  };

  /**
   * 배포 생성 제출 처리
   */
  const handleDeploySubmit = async (formData) => {
    const response = await callApi({
      url: `deployments?workspace_id=${workspaceId}`,
      method: 'POST',
      body: {
        deployment_name: formData.deployment_name,
        model_name: formData.model_name,
        model_id: formData.model_id,
        target_category: formData.target_category,
        target_device: formData.target_device,
        target_device_id: formData.target_device_id,
        serving_system: formData.serving_system,
        deploy_method: formData.deploy_method,
        workspace_id: workspaceId,
      },
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setIsWizardOpen(false);
      refreshData();
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  /**
   * 배포 API 코드 생성 모달 열기
   */
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

  const refreshData = () => {
    getDeploymentList();
  };

  useEffect(() => {
    loadModalComponent('UPLOAD_CHECKPOINT');
    loadModalComponent('EDIT_DEPLOYMENT');
    loadModalComponent('SERVING_CREATE_GROUP');
    loadModalComponent('SERVING_DELETE');
    loadModalComponent('TEMPLATE_CREATE');
    loadModalComponent('CREATE_DEPLOYMENT_API');
  }, []);

  useEffect(() => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Serving',
            t,
          },
        },
      ]),
    );
  }, [dispatch, t]);

  useEffect(() => {
    window.onbeforeunload = function () {
      sessionStorage.removeItem(`deployment/${workspaceId}_scroll_pos`);
    };
  }, [workspaceId]);

  return (
    <>
      <UserDeploymentContent
        watchFilterViewType={watchFilterViewType}
        deploymentList={listFilter(deploymentList)}
        isLoading={isLoading}
        openCreateDeploymentModal={openCreateDeploymentModal}
        openCreateApiCodeModal={openCreateApiCodeModal}
        refreshData={refreshData}
        // groupData={groupData}
        // getGroupData={getGroupData}
        // getTemplateData={getTemplateData}
        // clickedGroupId={clickedGroupId}
        // setClickedGroupId={setClickedGroupId}
        // templateData={templateData}
        // defaultGroupName={defaultGroupName}
        // defaultTemplateName={defaultTemplateName}
        // onClickNoGroup={onClickNoGroup}
        // noGroupSelectedStatus={noGroupSelectedStatus}
        // onClickGroupList={onClickGroupList}
        // selectedGroupData={selectedGroupData}
      />
      <NewDeploymentWizard
        isOpen={isWizardOpen}
        onClose={() => setIsWizardOpen(false)}
        onSubmit={handleDeploySubmit}
        workspaceId={workspaceId}
      />
    </>
  );
}

export default UserDeploymentPage;
