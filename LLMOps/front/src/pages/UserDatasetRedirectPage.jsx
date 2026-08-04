import React, { useLayoutEffect } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';

export default function UserDatasetRedirectPage() {
  const history = useHistory();
  const match = useRouteMatch();
  const { params } = match;
  const workspaceId = params.id;

  // 데이터 그룹 진입 시 첫 하위 탭으로 보낸다. 수집·라벨링·분석은 미노출로
  // 돌렸으므로(UserRouter routeArr) 유일한 가시 하위인 전처리로 보낸다 —
  // 미노출 탭으로 보내면 사이드바에 없는 화면이 열려 사용자가 길을 잃는다.
  useLayoutEffect(() => {
    history.push(`/user/workspace/${workspaceId}/datasets/process`);
  }, [history, workspaceId]);

  return <></>;
}
