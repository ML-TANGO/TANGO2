import React, { useLayoutEffect } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';

export default function UserDatasetRedirectPage() {
  const history = useHistory();
  const match = useRouteMatch();
  const { params } = match;
  const workspaceId = params.id;

  useLayoutEffect(() => {
    history.push(`/user/workspace/${workspaceId}/datasets/collect`);
  }, [history, workspaceId]);

  return <></>;
}
