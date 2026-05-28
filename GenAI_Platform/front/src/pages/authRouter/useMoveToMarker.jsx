import { useSelector } from 'react-redux';

const useMoveToMarker = () => {
  const auth = useSelector((state) => state.auth);
  const { userName } = auth;
  const { workspaceState } = useSelector((state) => ({
    workspaceState: state.workspace,
  }));

  const workspaces = workspaceState?.workspaces || [];

  const token = sessionStorage.getItem('token');
  const session = sessionStorage.getItem('loginedSession');

  const moveToMarker = ({ workspaceId }) => {
    const name = workspaces.filter((v) => v.id === Number(workspaceId))[0].name;
    const url = `${window.location.protocol}//${window.location.hostname}:${window.location.port}/`;

    window.open(
      `${url}marker/auth?user=${userName}&token=${token}&session=${session}&workspaceId=${workspaceId}&workspaceName=${name}`,
    );
  };

  return { moveToMarker };
};

export default useMoveToMarker;
