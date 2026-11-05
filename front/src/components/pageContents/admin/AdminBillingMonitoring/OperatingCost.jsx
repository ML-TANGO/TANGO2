import React from 'react';

import PeriodCostInfo from './operating/PeriodCostInfo';
import PeriodIncome from './operating/PeriodIncome';
import PeriodResource from './operating/PeriodResource';
import PublicResource from './operating/PublicResource';
import ResourceTable from './operating/ResourceTable';
import WorkspaceInfo from './operating/WorkspaceInfo';

import classNames from 'classnames/bind';
import style from './OperatingCost.module.scss';

const cx = classNames.bind(style);

const OperatingCost = () => {
  return (
    <div className={cx('container')}>
      <PeriodCostInfo />
      <WorkspaceInfo />
      <PeriodResource />
      <PeriodIncome />
      <PublicResource />
      <ResourceTable />
    </div>
  );
};

export default OperatingCost;
