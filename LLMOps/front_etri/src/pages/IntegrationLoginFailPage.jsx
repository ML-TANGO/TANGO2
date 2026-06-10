import { useCallback } from 'react';

// Component
import IntegrationLoginFailPageContent from '@src/components/pageContents/common/IntegrationLoginFailPageContent';

// Utils
import { redirectToPortal } from '@src/utils';

function IntegrationLoginFailPage() {
  const redirectPortal = useCallback(() => {
    redirectToPortal();
  }, []);

  return <IntegrationLoginFailPageContent redirectPortal={redirectPortal} />;
}

export default IntegrationLoginFailPage;
