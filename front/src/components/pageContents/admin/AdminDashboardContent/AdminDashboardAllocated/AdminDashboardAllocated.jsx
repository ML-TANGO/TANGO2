import { useEffect, useRef, useState } from 'react';
// i18n

import { useTranslation } from 'react-i18next';
import { connect } from 'react-redux';

import { convertByte } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDashboardAllocated.module.scss';

const cx = classNames.bind(style);

function AdminDashboardAllocated({ data, nodeInfo, storageData, t }) {
  // 색상 계산 함수

  // const resources = [
  //   { name: 'CPU', key: 'cpu' },
  //   { name: 'GPU', key: 'gpu' },
  //   { name: 'RAM', key: 'ram' },
  //   { name: 'STORAGE', key: 'storage' },
  // ];

  const getProgressColor = (percentage) => {
    if (percentage === 0) return '#c1c1c1';
    if (percentage > 0 && percentage <= 25) return '#2D76F8';
    if (percentage > 25 && percentage <= 50) return '#02E366';
    if (percentage > 50 && percentage <= 75) return '#FFEA53';
    if (percentage > 75) return '#FF3B30';
  };

  const RightSection = ({
    label,
    value = 0,
    percentage = 0,
    usage,
    unit = 'Cores',
  }) => {
    const newPercentage = isNaN(percentage) ? 0 : percentage;
    return (
      <>
        <div className={cx('progress-box')}>
          <div className={cx('progress-label')}>
            <div className={cx('label')}>{label}</div>
            <div className={cx('value')}>{value}</div>
          </div>
          <div className={cx('progress')}>
            <div
              className={cx('progress-bar')}
              style={{
                width: `${newPercentage}%`,
                backgroundColor: getProgressColor(newPercentage),
              }}
            ></div>
          </div>
        </div>
        <div className={cx('pcent')}>{Math.round(newPercentage)}%</div>
        <div className={cx('value')}>{usage}</div>
      </>
    );
  };

  return (
    <div className={cx('container')}>
      <div className={cx('title')}>자원별 할당 현황</div>
      <div className={cx('content')}>
        <div className={cx('left')}>
          <div className={cx('resource')}>CPU</div>
          <div className={cx('fig-box')}>
            <div className={cx('fig')}>
              <div className={cx('label')}>전체</div>
              <div className={cx('value')}>
                {nodeInfo?.cpu?.total ?? 0} Cores
              </div>
            </div>
            <div className={cx('fig')}>
              <div className={cx('label')}>잔여</div>
              <div className={cx('value')}>
                {nodeInfo?.cpu?.avail ?? 0} Cores
              </div>
            </div>
          </div>
        </div>
        <div className={cx('right')}>
          <div className={cx('alloc')}>
            <RightSection
              label={t('allocateGpu.label')}
              value={`${nodeInfo?.cpu?.alloc ?? 0} Cores`}
              percentage={(nodeInfo?.cpu?.alloc / nodeInfo?.cpu?.total) * 100}
              usage={`( ${nodeInfo?.cpu?.alloc ?? 0} Cores / ${Math.round(
                nodeInfo?.cpu?.total ?? 0,
              )} Cores)`}
            />
          </div>
          <div className={cx('br')}></div>
          <div className={cx('alloc')}>
            <RightSection
              label={t('used.label')}
              value={`${nodeInfo?.cpu?.used ?? 0} Cores`}
              percentage={(nodeInfo?.cpu?.used / nodeInfo?.cpu?.alloc) * 100}
              usage={`( ${nodeInfo?.cpu?.used ?? 0} Cores / ${Math.round(
                nodeInfo?.cpu?.alloc ?? 0,
              )} Cores)`}
            />
          </div>
        </div>
      </div>
      <div className={cx('content')}>
        <div className={cx('left')}>
          <div className={cx('resource')}>GPU</div>
          <div className={cx('fig-box')}>
            <div className={cx('fig')}>
              <div className={cx('label')}>전체</div>
              <div className={cx('value')}>{nodeInfo?.gpu?.total ?? 0} EA</div>
            </div>
            <div className={cx('fig')}>
              <div className={cx('label')}>잔여</div>
              <div className={cx('value')}>{nodeInfo?.gpu?.avail ?? 0} EA</div>
            </div>
          </div>
        </div>
        <div className={cx('right')}>
          <div className={cx('alloc')}>
            <RightSection
              label={t('allocateGpu.label')}
              value={`${nodeInfo?.gpu?.alloc ?? 0} EA`}
              percentage={(nodeInfo?.gpu?.alloc / nodeInfo?.gpu?.total) * 100}
              usage={`( ${nodeInfo?.gpu?.alloc ?? 0} EA / ${Math.round(
                nodeInfo?.gpu?.total ?? 0,
              )} EA )`}
            />
          </div>
          <div className={cx('br')}></div>
          <div className={cx('alloc')}>
            <RightSection
              label={t('used.label')}
              value={`${nodeInfo?.gpu?.used ?? 0} EA`}
              percentage={(nodeInfo?.gpu?.used / nodeInfo?.gpu?.alloc) * 100}
              usage={`( ${nodeInfo?.gpu?.used ?? 0} EA / ${Math.round(
                nodeInfo?.gpu?.alloc ?? 0,
              )} EA )`}
            />
          </div>
        </div>
      </div>
      <div className={cx('content')}>
        <div className={cx('left')}>
          <div className={cx('resource')}>RAM</div>
          <div className={cx('fig-box')}>
            <div className={cx('fig')}>
              <div className={cx('label')}>전체</div>
              <div className={cx('value')}>
                {convertByte(nodeInfo?.mem?.total ?? 0)}
              </div>
            </div>
            <div className={cx('fig')}>
              <div className={cx('label')}>잔여</div>
              <div className={cx('value')}>
                {convertByte(nodeInfo?.mem?.avail ?? 0)}
              </div>
            </div>
          </div>
        </div>
        <div className={cx('right')}>
          <div className={cx('alloc')}>
            <RightSection
              label={t('allocateGpu.label')}
              value={convertByte(nodeInfo?.mem?.alloc ?? 0)}
              percentage={(nodeInfo?.mem?.alloc / nodeInfo?.mem?.total) * 100}
              usage={`( ${convertByte(
                nodeInfo?.mem?.alloc ?? 0,
              )}  / ${convertByte(nodeInfo?.mem?.total ?? 0)} )`}
            />
          </div>
          <div className={cx('br')}></div>
          <div className={cx('alloc')}>
            <RightSection
              label={t('used.label')}
              value={convertByte(nodeInfo?.mem?.used ?? 0)}
              percentage={(nodeInfo?.mem?.used / nodeInfo?.mem?.alloc) * 100}
              usage={`( ${convertByte(
                nodeInfo?.mem?.used ?? 0,
              )}  / ${convertByte(nodeInfo?.mem?.alloc ?? 0)} )`}
            />
          </div>
        </div>
      </div>
      <div className={cx('content')}>
        <div className={cx('left')}>
          <div className={cx('resource')}>STORAGE</div>
          <div className={cx('fig-box')}>
            <div className={cx('fig')}>
              <div className={cx('label')}>전체</div>
              <div className={cx('value')}>
                {convertByte(storageData?.total_size ?? 0)}
              </div>
            </div>
            <div className={cx('fig')}>
              <div className={cx('label')}>잔여</div>
              <div className={cx('value')}>
                {convertByte(
                  storageData?.total_size - storageData?.total_alloc ?? 0,
                )}
              </div>
            </div>
          </div>
        </div>
        <div className={cx('right')}>
          <div className={cx('alloc')}>
            <RightSection
              label={t('allocateGpu.label')}
              value={convertByte(storageData?.total_alloc ?? 0)}
              percentage={
                (storageData?.total_alloc / storageData?.total_size) * 100
              }
              usage={`( ${convertByte(
                storageData?.total_alloc ?? 0,
              )}  / ${convertByte(storageData?.total_size ?? 0)} )`}
            />
          </div>
          <div className={cx('br')}></div>
          <div className={cx('alloc')}>
            <RightSection
              label={t('used.label')}
              value={convertByte(storageData?.total_used ?? 0)}
              percentage={
                (storageData?.total_used / storageData?.total_alloc) * 100
              }
              usage={`( ${convertByte(
                storageData?.total_used ?? 0,
              )}  / ${convertByte(storageData?.total_alloc ?? 0)} )`}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboardAllocated;
