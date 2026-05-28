import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './GpuNodeSelectBox.module.scss';

const cx = classNames.bind(style);

const GpuNodeSelectBox = ({
  gpuClusterList,
  handleSelectedGpuCluster,
  gpuUsingError,
  podGpuGcd,
  isShowPodGpuGcd = false,
}) => {
  const nodeGroupRef = useRef(null);
  const { t } = useTranslation();

  const gpuStatus = (value) => {
    if (value === 0) {
      return 'not-use';
    }

    if (value === 1) {
      return 'use';
    }

    if (value === 2) {
      return 'selected';
    }
  };

  useEffect(() => {
    if (gpuUsingError && nodeGroupRef.current) {
      nodeGroupRef.current.scrollLeft = 0;
    }
  }, [gpuUsingError]);

  return (
    <div className={cx('gpu-node-container')}>
      <div className={cx('header')}>
        <div className={cx('title')}>{t('selectGpu.label')}</div>
        <div className={cx('condition')}>
          <div className={cx('desc')}>
            <div className={cx('circle', 'not-use')}></div>
            <span className={cx('not-use')}>{t('currentAvailableCount')}</span>
          </div>
          <div className={cx('desc')}>
            <div className={cx('circle', 'use')}></div>
            <span className={cx('use')}>{t('active')}</span>
          </div>
          <div className={cx('desc')}>
            <div className={cx('circle', 'selected')}></div>
            <span className={cx('selected')}>{t('selectComplete.label')}</span>
          </div>
        </div>
      </div>
      {gpuClusterList.length === 0 && (
        <div className={cx('empty-notice')}>
          GPU 정보를 불러오는 중입니다. 잠시만 기다려주세요.
        </div>
      )}
      {gpuClusterList.length > 0 && (
        <div
          className={cx('node-group')}
          style={{
            gridTemplateColumns: `repeat(${gpuClusterList.length}, 140px)`,
          }}
          ref={nodeGroupRef}
        >
          {gpuClusterList.map(({ nodeName, gpuList }) => {
            return (
              <div className={cx('node-list')} key={nodeName}>
                <div className={cx('node-name')}>{nodeName}</div>
                <div className={cx('gpu-list')}>
                  {gpuList.map(({ gpu_name, gpu_uuid, used, originUsed }) => {
                    return (
                      <div
                        className={cx('gpu', `${gpuStatus(used)}`)}
                        key={gpu_uuid}
                        onClick={() =>
                          handleSelectedGpuCluster({
                            gpu_name,
                            gpu_uuid,
                            used,
                            originUsed,
                            nodeName,
                          })
                        }
                        data-gpu-name={gpu_name}
                      >
                        {gpu_name.length < 15
                          ? gpu_name
                          : `${gpu_name.slice(0, 15)}...`}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {gpuUsingError && <span className={cx('warning')}>{gpuUsingError}</span>}
      {isShowPodGpuGcd && (
        <div className={cx('pod-gpu')}>
          <span className={cx('desc-text')}>{t('podGpuCount.desc')}</span>
          <span>{`${podGpuGcd}`}</span>
        </div>
      )}
    </div>
  );
};

export default GpuNodeSelectBox;
