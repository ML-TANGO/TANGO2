import {
  Header,
  PageTemplate,
  PageTemplateProvider,
  SideNav,
} from '@tango/ui-react';

import LangSetting from '@src/components/Frame/Header/LangSetting';
// Components
import UserSetting from '@src/components/Frame/Header/UserSetting';

// Theme
import { theme } from '@src/utils';

const UI = () => {
  const rightBoxContents = [<UserSetting />, <LangSetting />];

  return (
    <PageTemplateProvider>
      <PageTemplate
        theme={theme.PRIMARY_THEME}
        headerRender={(isOpen, expandHandler) => (
          <Header
            theme={theme.PRIMARY_THEME}
            isOpen={isOpen}
            expandHandler={expandHandler}
            rightBoxContents={rightBoxContents}
          />
        )}
        sideNavRender={(isOpen) => (
          <SideNav
            theme={theme.PRIMARY_THEME}
            isOpen={isOpen}
            navList={[
              { name: 'Dashboard', path: '/user/dashboard' },
              { name: 'Dashboard', path: '/user/dashboard' },
              { name: 'Dashboard', path: '/user/dashboard' },
            ]}
          />
        )}
      >
        {new Array(1000).fill(`아아아<br />`)}
      </PageTemplate>
    </PageTemplateProvider>
  );
};

export default UI;
