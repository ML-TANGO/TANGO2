import { useEffect } from 'react';

import UserDatasetCollectMenuContent from '@src/components/pageContents/user/UserDatasetCollectMenuContent';

import { loadModalComponent } from '@src/modal';

export default function UserDataCollectMenuPage() {
  useEffect(() => {
    loadModalComponent('DATA_COLLECT_MODAL');
    loadModalComponent('EDIT_DATA_COLLECT_MODAL');
    loadModalComponent('ADD_WEB_CROWLER_MODAL');
    loadModalComponent('ADD_REMOTE_SERVERL');
    loadModalComponent('ADD_DEPLOY_PROJECT');
    loadModalComponent('ADD_PUBLIC_API_MODAL');
  }, []);

  return <UserDatasetCollectMenuContent />;
}
