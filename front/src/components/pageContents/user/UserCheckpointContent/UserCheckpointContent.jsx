// Components
import Button from '@src/components/atoms/button/Button';
import Tab from '@src/components/molecules/Tab'; // 탭 컴포넌트 추후 변경

import AllCkpListTab from './AllCkpListTab';
import RegisteredCkpListTab from './ResiteredCkpListTab/RegisteredCkpListTab';

/**
 * 노드 관리자 페이지 컨텐츠 컴포넌트
 * @param {{
 *  tab: 'REGISTERED_CKP_LIST' | 'ALL_CKP_LIST',
 *  tabOptions: [
 *    { label: string, value: 'ALL_CKP_LIST' },
 *    { label: string, value: 'ALL_CKP_LIST' },
 *  ],
 *  tabHandler: (selectedTab : 'REGISTERED_CKP_LIST' | 'ALL_CKP_LIST') => {},
 *  openDNAModelModal: function,
 * }} param
 */
function UserCheckpointContent({
  tab,
  tabOptions,
  tabHandler,
  openDNAModelModal,
}) {
  const renderTabContent = (targetTab) => {
    if (targetTab === 'REGISTERED_CKP_LIST') {
      return <RegisteredCkpListTab />;
    }
    if (targetTab === 'ALL_CKP_LIST') {
      return <AllCkpListTab />;
    }

    return <div>Not Found</div>;
  };

  return (
    <div>
      <div>
        <Button onClick={openDNAModelModal}>Upload DNA Model</Button>
      </div>
      <Tab
        type='c'
        sidePaddingNone
        option={tabOptions}
        select={{ value: tab }}
        tabHandler={({ value: selectedTab }) => {
          tabHandler(selectedTab);
        }}
      />
      {renderTabContent(tab)}
    </div>
  );
}

export default UserCheckpointContent;
