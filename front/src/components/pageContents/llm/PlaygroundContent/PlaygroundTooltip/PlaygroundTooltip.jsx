import tooltipIcon from '@src/static/images/icon/00-gray-tooltip-icon.svg';
import React, { useRef, useState } from 'react';

import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';

import TooltipPortal from '@src/hooks/TooltipPortal';

const PlaygroundTooltip = ({ content }) => {
  const tooltipRef = useRef(null);
  const [isShowTooltip, setIsShowTooltip] = useState(false);
  return (
    <>
      <img
        ref={tooltipRef}
        src={tooltipIcon}
        alt='tooltip-icon'
        onMouseEnter={() => setIsShowTooltip(true)}
        onMouseLeave={() => setIsShowTooltip(false)}
      />
      <TooltipPortal
        direction='bottom'
        targetRef={tooltipRef}
        isShowTooltip={isShowTooltip}
      >
        <DarkTooltip
          direction='bottom'
          tooltipColor='#c1c1c1'
          content={
            <div
              style={{
                display: 'flex',
                minWidth: '32px',
                fontFamily: 'SpoqaM',
                fontSize: '10px',
                justifyContent: 'center',
                color: '#fff',
              }}
            >
              {content}
            </div>
          }
        />
      </TooltipPortal>
    </>
  );
};

export default PlaygroundTooltip;
