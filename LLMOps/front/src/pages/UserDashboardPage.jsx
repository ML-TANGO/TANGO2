import { useEffect, useState } from 'react';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';
import { useHistory } from 'react-router-dom';

// Components
import UserDashboardContent from '@src/components/pageContents/user/UserDashboardContent';

// Actions
import { startPath } from '@src/store/modules/breadCrumb';
import { getWorkspacesAsync } from '@src/store/modules/workspace';
import { loadModalComponent } from '@src/modal';

function UserDashboardPage({ trackingEvent }) {
  // Router Hooks
  const history = useHistory();

  // Redux hooks
  const dispatch = useDispatch();

  // State
  const { workspaces } = useSelector((state) => state.workspace);
  const { workspace: workspaceAlarm } = useSelector(
    (state) => state.alarmNotice,
    shallowEqual,
  );

  const [serverError, setServerError] = useState(false);

  /**
   * API 호출 GET
   * 사용자 대시보드 데이터 가져오기
   */
  const getDashboardData = async () => {
    if (!workspaces) {
      setServerError(true);
      return;
    }

    dispatch(getWorkspacesAsync());
  };

  /**
   * 새로고침
   */
  const onRefresh = () => {
    getDashboardData();
    trackingEvent({
      category: 'User Dashboard Page',
      action: 'Refresh Dashboard Data',
    });
  };

  /**
   * 워크스페이스 바로가기
   *
   * @param {number} workspace 워크스페이스 ID
   */
  const moveWorkspace = (workspace) => {
    trackingEvent({
      category: 'User Dashboard Page',
      action: 'Move To Workspace Home Page',
    });
    history.push({
      pathname: `workspace/${workspace.id}/selected`,
      state: {
        id: workspace.id,
        name: workspace.name,
        loc: ['Home'],
      },
    });
  };

  useEffect(() => {
    loadModalComponent('CREATE_WORKSPACE');
    dispatch(
      startPath([
        {
          component: {
            name: '',
          },
        },
      ]),
    );
    // 2번 호출됨에 따른 주석처리
    // getDashboardData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    getDashboardData();
  }, [workspaceAlarm]);

  return (
    <UserDashboardContent
      data={workspaces}
      onRefresh={onRefresh}
      moveWorkspace={moveWorkspace}
      serverError={serverError}
      getDashboardData={getDashboardData}
    />
  );
}

export default UserDashboardPage;
