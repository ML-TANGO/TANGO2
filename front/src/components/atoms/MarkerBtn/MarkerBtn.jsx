import { useRouteMatch } from 'react-router-dom';
import { useSelector } from 'react-redux';

const ModalOpenButton = ({
  disabled,
  workspaceName,
  datasetId,
  datasetName,
}) => {
  const match = useRouteMatch();
  const auth = useSelector((state) => state.auth);
  const { userName } = auth;
  const token = sessionStorage.getItem('token');
  const session = sessionStorage.getItem('loginedSession');

  const MARKER_URL =
    import.meta.env.VITE_REACT_APP_MARKER_API_HOST || 'http://localhost:9999/';
  const LOCAL_HOST = 'http://localhost:9999/';

  const moveToMarker = () => {
    const { id: wId } = match.params;
    window.open(
      `${MARKER_URL}auth?user=${userName}&token=${token}&session=${session}&workspaceId=${wId}&workspaceName=${workspaceName}&datasetId=${datasetId}&datasetName=${datasetName}`,
    );
  };
  const moveToDev = () => {
    const { id: wId } = match.params;
    window.open(
      `${LOCAL_HOST}auth?user=${userName}&token=${token}&session=${session}&workspaceId=${wId}&workspaceName=${workspaceName}&datasetId=${datasetId}&datasetName=${datasetName}`,
    );
  };

  return (
    <button
      className='table-icon-marker'
      onClick={moveToMarker}
      disabled={disabled}
    >
      <img
        src='/images/logo/BI_Marker.svg'
        alt='Jonathan Marker'
        className='marker-logo'
      />
      <img
        src='/images/icon/00-ic-basic-arrow-02-right.svg'
        alt='>'
        className='right'
      />
    </button>
  );
};

export default ModalOpenButton;
