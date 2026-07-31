import React from 'react';

import DatasetCom from './DatasetCom';
import PromptCom from './PromptCom';
import ExternalTestCom from './ExternalTestCom';

// CSS module
import classNames from 'classnames/bind';
import style from './TestComponent.module.scss';

const cx = classNames.bind(style);

export default function TestComponent({
  integratedTestValue,
  playgroundId,
  isExternal,
}) {
  if (isExternal) {
    return (
      <div className={cx('flex-cont')}>
        <ExternalTestCom playgroundId={playgroundId} />
      </div>
    );
  }
  return (
    <div className={cx('flex-cont')}>
      {integratedTestValue && <DatasetCom playgroundId={playgroundId} />}
      {!integratedTestValue && <PromptCom playgroundId={playgroundId} />}
    </div>
  );
}
