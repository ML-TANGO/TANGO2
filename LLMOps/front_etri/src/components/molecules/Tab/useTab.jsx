import { useState } from 'react';

// Components
import Tab from './Tab';

function useTab(options) {
  const [tab, setTab] = useState(options[0]);

  const tabHandler = (t) => {
    setTab(t);
  };

  const renderTab = () => (
    <Tab option={options} select={tab} tabHandler={tabHandler} />
  );

  return [tab, renderTab];
}

export default useTab;
