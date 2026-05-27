import { useRouteMatch } from 'react-router-dom';

// Components
import HpsContent from '@src/components/pageContents/user/UserHpsContent';

function UserHpsPage() {
  const match = useRouteMatch();
  const { id: wid, tid } = match.params;

  return <HpsContent wid={wid} tid={tid} />;
}

export default UserHpsPage;
