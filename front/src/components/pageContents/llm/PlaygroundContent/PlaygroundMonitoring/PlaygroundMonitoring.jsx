import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRouteMatch } from 'react-router-dom';
import { toast } from 'react-toastify';

import { getMonitoringId } from '@src/apis/llm/playground';
import { STATUS_SUCCESS } from '@src/network';
import DeployDashboardPage from '@src/pages/DeployDashboardPage';

const stateStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '240px',
  color: '#747474',
  fontFamily: 'SpoqaM',
  fontSize: '14px',
};

// 배포 상세의 원본 playgroundId 를 모니터링 대시보드가 쓰는 deployment_id 로
// 해석한 뒤, 대시보드를 탭 안에 임베드한다. (기존 별도 라우트 대체)
const PlaygroundMonitoring = ({
  workspaceId: workspaceIdProp,
  playgroundId: playgroundIdProp,
}) => {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const workspaceId = workspaceIdProp ?? match.params.id;
  const playgroundId = playgroundIdProp ?? match.params.did;

  const [deploymentId, setDeploymentId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    const resolveDeploymentId = async () => {
      setIsLoading(true);
      const { status, result, message } = await getMonitoringId(playgroundId);
      if (ignore) return;

      if (status === STATUS_SUCCESS && result?.playground_id) {
        setDeploymentId(result.playground_id);
      } else {
        toast.error(message || t('playground.header.deploy.message'));
      }
      setIsLoading(false);
    };

    resolveDeploymentId();

    return () => {
      ignore = true;
    };
  }, [playgroundId, t]);

  if (isLoading) {
    return <div style={stateStyle}>불러오는 중...</div>;
  }

  if (!deploymentId) {
    return (
      <div style={stateStyle}>{t('playground.header.deploy.message')}</div>
    );
  }

  return (
    <DeployDashboardPage
      embedded
      deploymentId={deploymentId}
      workspaceId={workspaceId}
    />
  );
};

export default PlaygroundMonitoring;
