import { Badge } from '@tango/ui-react';

import React from 'react';

import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

import classNames from 'classnames/bind';
import style from './DashboardProjectInstance.module.scss';

const cx = classNames.bind(style);

const exampleArr = [
  {
    instanceType: '모델',
    projectName: '모델 카드 이름',
    instanceName: 'TITAN RTX.1.1.4',
    countValue: 2,
  },
  {
    instanceType: 'RAG',
    projectName: 'RAG 카드 이름',
    instanceName: 'TITAN RTX.1.1.4',
    countValue: 2,
  },
  {
    instanceType: '플레이그라운드',
    projectName: '플레이그라운드 카드 이름',
    instanceName: 'TITAN RTX.1.1.4',
    countValue: 100,
  },
];
const tripleArr = [...exampleArr, ...exampleArr, ...exampleArr];

export default function DashboardProjectInstance() {
  return (
    <div className={cx('dashboard-frame-cont')}>
      <div className={cx('title-cont')}>프로젝트별 인스턴스 할당 현황</div>
      <div className={cx('thead')}>
        <div className={cx('tr')}>
          <div className={cx('td')}>프로젝트 이름</div>
          <div className={cx('td')}>인스턴스 이름</div>
          <div className={cx('td')}>개수</div>
        </div>
      </div>
      <div className={cx('tbody')}>
        {tripleArr.map((info, idx) => {
          const { instanceType, projectName, instanceName, countValue } = info;
          return (
            <div className={cx('tr')} key={idx}>
              <div className={cx('td')}>
                <Badge label={instanceType} size='lg' type='orange' />
                <span className={cx('projectName-txt')}>{projectName}</span>
              </div>
              <div className={cx('td')}>
                <span className={cx('instanceName-txt')}>T{instanceName}</span>
                <InstanceTooltip />
              </div>
              <div className={cx('td')}>{countValue}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
