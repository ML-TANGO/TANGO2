import React from 'react';

import RagDocs from './RagDocs';
import RagSearch from './RagSearch';
import RagSetting from './RagSetting';

export default function RagContent({ selectedTab }) {
  return (
    <>
      {selectedTab === 0 && <RagSetting selectedTab={selectedTab} />}
      {selectedTab === 1 && <RagSearch selectedTab={selectedTab} />}
      {selectedTab === 2 && <RagDocs selectedTab={selectedTab} />}
    </>
  );
}
