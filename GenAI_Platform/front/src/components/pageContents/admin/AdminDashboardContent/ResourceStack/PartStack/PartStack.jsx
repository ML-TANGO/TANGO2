import React, { useRef, useState, useTransition } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

import { convertBinaryByte } from '@src/utils';

import { BAR_COLOR } from '../ResourceStack';

import classNames from 'classnames/bind';
import style from './PartStack.module.scss';

const cx = classNames.bind(style);

const PartStack = ({ idx, stackInfo, width, type, unit }) => {
  const { t } = useTranslation();
  const { name, used, manager, usedPcent, allocPcent } = stackInfo;

  const stackRef = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);

  return (
    <React.Fragment key={`${idx}-${name}-${used}`}>
      <div
        ref={stackRef}
        className={cx('stack-part-cont')}
        style={{
          width: `${width}px`,
          backgroundColor: BAR_COLOR[idx],
        }}
        onMouseEnter={() => setIsShowTooltip(true)}
        onMouseLeave={() => setIsShowTooltip(false)}
      />
      <TooltipPortal
        direction='top'
        targetRef={stackRef}
        isShowTooltip={isShowTooltip}
      >
        <DarkTooltip
          direction='top'
          content={
            <div
              style={{
                display: 'flex',
                gap: '8px',
                fontFamily: 'SpoqaB',
                fontSize: '10px',
              }}
            >
              <div className={cx('tooltip-box')}>
                <div className={cx('top')}>
                  <span>{name}</span>
                  {manager ?? <span>{manager}</span>}
                  {/* <span>{type === 'used' ? usedPcent : allocPcent} %</span> */}
                  <span>{usedPcent} %</span>
                </div>
                <div style={{ border: '1px solid #fff', margin: '8px 0px' }} />

                <div className={cx('bottom')}>
                  {type === 'used' ? (
                    <>
                      <span style={{ marginRight: '8px' }}>
                        {t('used.label')}
                      </span>
                      {unit !== 'GB'
                        ? `${used ?? 0}`
                        : convertBinaryByte(used ?? 0)}
                      {unit !== 'GB' && (
                        <span style={{ marginLeft: '6px' }}>{unit}</span>
                      )}
                    </>
                  ) : (
                    <>
                      <span style={{ marginRight: '8px' }}>
                        {t('allocateGpu.label')}
                      </span>
                      {unit !== 'GB'
                        ? `${used ?? 0}`
                        : convertBinaryByte(used ?? 0)}
                      {unit !== 'GB' && (
                        <span style={{ marginLeft: '6px' }}>{unit}</span>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          }
        />
      </TooltipPortal>
    </React.Fragment>
  );
};

export default PartStack;
