// Components
import { loadModalComponent } from '@src/modal';
import { useEffect } from 'react';

import LoginContent from '@src/components/pageContents/common/LoginContent';

function LoginPage() {
  useEffect(() => {
    loadModalComponent('SIGNUP_MODAL');
  }, []);

  return <LoginContent />;
}

export default LoginPage;
