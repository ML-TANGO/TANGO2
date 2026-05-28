import React, { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import classNames from 'classnames/bind';
import style from './ProjectStack.module.scss';

const cx = classNames.bind(style);

export const BAR_COLOR = [
  '#DEE9FF',
  '#C8DBFD',
  '#93BAFF',
  '#2D76F8',
  '#164ABE',
  '#002F77',
  '#042659',
  '#C1C1C1',
  '#747474',
  '#3E3E3E',
  '#7E7E7F',
  '#FFF8D9',
  '#FFE6B0',
  '#FFD488',
  '#FFC260',
  '#FFB038',
  '#FF9E10',
  '#FF7A00',
  '#E3FCEE',
  '#C3F2D5',
  '#A3E8BC',
  '#83DFA3',
  '#63D58A',
  '#00C775',
  '#00C775',
];

const caltotalRate = (usedRateList) => {
  const shallowCopyList = usedRateList.slice();
  const totalRate = shallowCopyList.reduce((acc, cur) => {
    acc += cur.used_rate;
    return acc;
  }, 0);
  return totalRate;
};

const ProjectStack = ({ used_rate: usedRateList, remaining_resource }) => {
  const { t } = useTranslation();
  const totalRete = caltotalRate(usedRateList);
  const { cpu, gpu, ram } = remaining_resource;

  const remainStackRef = useRef(null);
  const [remainVisible, setRemainVisible] = useState(false);

  return (
    <div className={cx('stack-wrap')}>
      <div className={cx('stack')}>
        {usedRateList.map(
          ({ item_name, used_rate, used_resource, item_user }, index) => (
            <ProjectRate
              projectName={item_name}
              user={item_user}
              usedRate={used_rate}
              gpu={used_resource.gpu}
              cpu={used_resource.cpu}
              ram={used_resource.ram}
              order={index}
              key={index}
              leftPercent={
                usedRateList
                  .slice(0, index + 1)
                  .map((data) => data.used_rate)
                  .reduce((prev, cur) => prev + cur, 0) -
                usedRateList[index].used_rate / 2
              }
            />
          ),
        )}
        <div
          className={cx('remain')}
          style={{ width: `${100 - totalRete.toFixed(0)}%` }}
          ref={remainStackRef}
          onMouseEnter={() => setRemainVisible(true)}
          onMouseLeave={() => setRemainVisible(false)}
        />
        <TooltipPortal
          direction='bottom'
          targetRef={remainStackRef}
          isShowTooltip={remainVisible}
        >
          <DarkTooltip
            direction='bottom'
            content={
              <div className={cx('tool-tip')}>
                <div className={cx('basic-info')}>
                  <span>{t('availableCapacity.label')}</span>
                  <span>{100 - totalRete.toFixed(0)}%</span>
                </div>
                <div className={cx('middle-line')}></div>
                <div className={cx('instance-info')}>
                  <div className={cx('resource')}>
                    <span>vGPU</span>
                    <span>vCPU</span>
                    <span>RAM</span>
                  </div>
                  <div className={cx('value')}>
                    <span>{gpu ? gpu : '-'} EA</span>
                    <span>{cpu ? cpu : '-'} Cores</span>
                    <span>{ram ? ram : '-'} GB</span>
                  </div>
                </div>
              </div>
            }
          />
        </TooltipPortal>
      </div>
      <span className={cx('rate')}>{totalRete.toFixed(0)}%</span>
    </div>
  );
};

const ProjectRate = ({ projectName, user, usedRate, gpu, cpu, ram, order }) => {
  const stackRef = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  const showTooltip = () => {
    setIsVisible(true);
  };

  const hideTooltip = () => {
    setIsVisible(false);
  };

  return (
    <>
      <div
        ref={stackRef}
        className={cx('project-info')}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        style={{
          width: `${usedRate}%`,
          backgroundColor: BAR_COLOR[order % 26],
        }}
      />
      <TooltipPortal
        direction='bottom+6'
        targetRef={stackRef}
        isShowTooltip={isVisible}
      >
        <DarkTooltip
          direction='bottom'
          content={
            <div className={cx('tool-tip')}>
              <div className={cx('basic-info')}>
                <span>{projectName}</span>
                <span>{user}</span>
                <span>{usedRate.toFixed(2)}%</span>
              </div>
              <div className={cx('middle-line')}></div>
              <div className={cx('instance-info')}>
                <div className={cx('resource')}>
                  <span>vGPU</span>
                  <span>vCPU</span>
                  <span>RAM</span>
                </div>
                <div className={cx('value')}>
                  <span>{gpu ? `${gpu} EA` : '-'}</span>
                  <span>{cpu ? `${cpu} Cores` : '-'}</span>
                  <span>{ram ? `${ram} GB` : '-'}</span>
                </div>
              </div>
            </div>
          }
        />
      </TooltipPortal>
    </>
  );
};

export default ProjectStack;
