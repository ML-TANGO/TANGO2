import React, { memo } from 'react';

import PartFrame from '../PartFrame';

export default memo(({ data }) => {
  const { subTitle, isStopBtn } = data;
  return <PartFrame subTitle={subTitle} isStopBtn={isStopBtn} />;
});
