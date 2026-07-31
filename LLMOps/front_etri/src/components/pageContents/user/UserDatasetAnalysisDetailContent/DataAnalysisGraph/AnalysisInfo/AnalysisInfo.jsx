import React from 'react';
import { useTranslation } from 'react-i18next';

import Info from './Info';
import InstanceSetting from './InstanceSetting';

import classNames from 'classnames/bind';
import style from './AnalysisInfo.module.scss';

const cx = classNames.bind(style);

export default function AnalysisInfo({ infoData, originGraphData }) {
  const { t } = useTranslation();

  return (
    <div
      className={cx(originGraphData.length === 0 ? 'flex-746' : 'flex-1140')}
    >
      <Info infoData={infoData} originGraphData={originGraphData} />
      <InstanceSetting infoData={infoData} />
    </div>
  );
}
