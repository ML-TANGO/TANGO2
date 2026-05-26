import { loadModalComponent } from '@src/modal';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useHistory, useRouteMatch } from 'react-router-dom';

// Components
import UserTrainingContent from '@src/components/pageContents/user/UserTrainingContent';

import { startPath } from '@src/store/modules/breadCrumb';
// Actions
import { openModal } from '@src/store/modules/modal';
// Custom Hooks
import useIntervalCall from '@src/hooks/useIntervalCall';

// network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import {
  errorToastMessage,
  scrollToPrevPosition,
  sortDescending,
} from '@src/utils';

/**
 * 유저 학습 목록 페이지
 * @component
 * @example
 *
 * return (
 *  <UserTrainingPage />
 * );
 *
 *
 * -
 */
function UserTrainingPage() {
  const { t } = useTranslation();
  const history = useHistory();
  const { breadCrumb } = useSelector((state) => state);

  // 컴포넌트 상태
  const [isLoading, setIsLoading] = useState(true); // 학습 목록 조회 로딩 여부 (boolean)
  const [trainingList, setTrainingList] = useState([]); // 학습 목록 값 (Array)
  const [selectedFilter, setSelectedFilter] = useState([]); // 체크된 필터 목록 (Array<{ label: string, value: string }>)
  const [keywordFilter, setKeywordFilter] = useState(''); // 검색 필터 (string)
  const [selectedViewType, setSelectedViewType] = useState(''); // 선택된 뷰 타입 ({ name: string, value: any, iconPath: string, selected: boolean })
  const [instanceInfo, setInstanceInfo] = useState({});

  // Redux Hooks
  const dispatch = useDispatch();

  // Router Hooks
  const match = useRouteMatch();
  const { id: workspaceId } = match.params; // 브라우저 url의 path 파라미터의 워크스페이스 id 값

  const breadCrumbHandler = useCallback(() => {
    dispatch(
      startPath([
        {
          component: {
            name: 'Training',
            t,
          },
        },
      ]),
    );
  }, [dispatch, t]);

  /**
   * 학습 목록 조회
   */
  const getTrainingList = useCallback(async () => {
    // workspaceId로 학습목록 다가져옴
    const response = await callApi({
      url: `projects?workspace_id=${workspaceId}`,
      method: 'GET',
    });
    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      const sortList = sortDescending(result.list.reverse(), 'bookmark');

      setTrainingList(sortList);
      setIsLoading(false);
      return true;
    } else {
      errorToastMessage(error, message);
    }
    return false;
  }, [workspaceId]);

  useIntervalCall(getTrainingList, 1000, () => {
    const path = sessionStorage.getItem(`training/${workspaceId}_scroll_pos`);
    if (history.action === 'POP' && path) {
      const path = `training/${workspaceId}`;
      scrollToPrevPosition(path);
    } else {
      // * 스토리지 저장된거 삭제
      sessionStorage.removeItem(`training/${workspaceId}_scroll_pos`);
    }

    if (breadCrumb?.length > 1) {
      breadCrumbHandler();
    }
  });

  // 학습 목록 필터링
  const listFilter = (trainingList) => {
    // 빌트인 모델 명, 학습 소유자 명, 학습 이름
    return trainingList.filter(
      ({
        built_in_model_name: builtInModelName = '',
        user_name: user = '',
        name = '',
        status: { workbench },
        permission_level: permissionLevel,
        type,
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
            (name &&
              name.toLowerCase().indexOf(keywordFilter.toLowerCase()) !== -1)
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
            if (workbench !== 'running') activatedFilterFlag = false;
          } else if (value === 'DEACTIVATED') {
            // 자원 미사용
            if (workbench === 'running') deActivatedFilterFlag = false;
          } else if (value === 'BUILT_IN') {
            // 빌트인 타입
            if (type !== 'built-in') builtInFilterFlag = false;
          } else if (value === 'CUSTOM') {
            // 커스텀 타입
            if (type !== 'advanced') customFilterFlag = false;
          } else if (value === 'ACCESSIBLE') {
            // 접근 가능
            if (permissionLevel === 0) accessibleFilterFlag = false;
          } else if (value === 'INACCESSIBLE') {
            // 접근 불가능
            if (permissionLevel !== 0) accessibleFilterFlag = false;
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
    ({ filter, viewType, search }) => {
      if (filter) setSelectedFilter(filter);
      if (viewType) setSelectedViewType(viewType.value);
      if (search !== undefined) setKeywordFilter(search);
    },
    [setSelectedFilter, setSelectedViewType],
  );

  /**
   * 학습 생성 모달 열기
   */
  const openCreateTrainingModal = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_TRAINING',
        modalData: {
          submit: {
            text: 'create.label',
          },
          cancel: {
            text: 'cancel.label',
          },
          workspaceId,
        },
      }),
    );
  };

  const refreshData = () => {
    getTrainingList();
  };

  useEffect(() => {
    loadModalComponent('UPLOAD_CHECKPOINT');
    loadModalComponent('CREATE_TRAINING');
    loadModalComponent('TOOL_PASSWORD_CHANGE');
  }, []);

  useEffect(() => {
    breadCrumbHandler();
  }, [breadCrumbHandler]);

  // useEffect(() => {
  //   if (scrollInfos && match?.isExact) {
  //     window.scrollTo(0, scrollInfos);
  //     const scrollTop = Math.max(
  //       document.documentElement.scrollTop,
  //       document.body.scrollTop,
  //     );
  //     // 현재위치와 복구위치가 같다면
  //     if (scrollTop === scrollInfos) {
  //       scrollRemove();
  //     }
  //   }
  //   // 의존성 배열에 fetching 해오는 데이터를 넣어준다.
  // }, [scrollInfos, scrollRemove, match]);

  return (
    <UserTrainingContent
      watchFilterViewType={watchFilterViewType}
      trainingList={listFilter(trainingList)}
      isLoading={isLoading}
      selectedViewType={selectedViewType}
      openCreateTrainingModal={openCreateTrainingModal}
      refreshData={refreshData}
    />
  );
}

export default UserTrainingPage;
