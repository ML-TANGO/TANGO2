import React from 'react';
import {
  buildStyles,
  CircularProgressbarWithChildren,
} from 'react-circular-progressbar';

const calStatusColor = (percentage) => {
  if (percentage > 75) {
    return { path: '#FA4E57', trail: '#F0F0F0' };
  }

  if (percentage > 50) {
    return { path: '#FFEA53', trail: '#F0F0F0' };
  }

  if (percentage > 0) {
    return { path: '#2D76F8', trail: '#F0F0F0' };
  }

  return { path: '#F0F0F0', trail: '#F0F0F0' };
};

export const calPercent = (total, used) => {
  if (Number(total) === 0) return { percentage: 0 };
  const percentage = ((Number(used) / Number(total)) * 100).toFixed(0);
  return { percentage: percentage ? percentage : 0 };
};

const CircleGauge = React.memo(({ percentage, children }) => {
  const { path, trail } = calStatusColor(percentage);

  return (
    <CircularProgressbarWithChildren
      value={percentage}
      styles={buildStyles({
        textColor: '#212121',
        pathColor: path,
        trailColor: trail,
        strokeLinecap: 'round',
      })}
      strokeWidth={9}
    >
      {children}
    </CircularProgressbarWithChildren>
  );
});

export default CircleGauge;
