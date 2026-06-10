import React from 'react';

import PromptCommitList from './PromptCommitList';
import PromptInfo from './PromptInfo';

export default function PromptContent({ selectedTab }) {
  return (
    <>
      {selectedTab === 0 && <PromptInfo selectedTab={selectedTab} />}
      {selectedTab === 1 && <PromptCommitList />}
    </>
  );
}
