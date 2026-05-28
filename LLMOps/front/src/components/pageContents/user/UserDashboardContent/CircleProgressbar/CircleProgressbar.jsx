import { Tooltip } from '@jonathan/ui-react';

import CircleGauge from '@src/components/molecules/CircleGauge';

export const calPercent = (total, used) => {
  if (Number(total) === 0) return { percentage: 0 };
  const percentage = ((Number(used) / Number(total)) * 100).toFixed(0);
  return { percentage: percentage ? percentage : 0 };
};

const CircleProgressbar = ({ total, used, toolTipStyle }) => {
  const maxLength = total.toString().length + used.toString().length;
  const { percentage } = calPercent(total, used);

  return (
    <CircleGauge percentage={percentage}>
      {/* 말줄임 표시될 때 툴팁 표시 */}
      {maxLength > 4 && (
        <Tooltip
          contents={
            <span style={{ fontFamily: 'SpoqaM', fontSize: '14px' }}>
              {used}/{total}
            </span>
          }
          contentsCustomStyle={{
            minWidth: '100%',
            textAlign: 'center',
            border: '0.5px solid #DEE9FF',
            borderRadius: '4px',
            boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
            padding: '16px',
            fontSize: '16px',
            fontWeight: 500,
            ...toolTipStyle,
          }}
          iconCustomStyle={{
            width: '24px',
            marginLeft: '2px',
          }}
          globalCustomStyle={{
            width: '100px',
            position: 'absolute',
          }}
          customStyle={{
            opacity: 0,
          }}
        />
      )}
      <div
        style={{
          width: '100px',
          textAlign: 'center',
          fontSize: maxLength > 2 ? '16px' : '24px',
          marginTop: '-13px',
          color: '#3e3e3d',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {maxLength > 4 ? '• • •' : `${Number(used)}/${Number(total)}`}
      </div>
    </CircleGauge>
  );
};

export default CircleProgressbar;
