import { buildStyles, CircularProgressbar } from 'react-circular-progressbar';

const CircleProgressbar = ({ total, used }) => {
  let percentage = 0;
  if (Number(total) !== 0) {
    percentage = ((Number(used) / Number(total)) * 100).toFixed(0);
  }
  let path = '';
  let trail = '';
  if (percentage <= 25) {
    path = '#00e451';
    trail = '#d9fbe5';
  } else if (percentage <= 50) {
    path = '#ffbd31';
    trail = '#ffeecb';
  } else {
    path = '#ff5953';
    trail = '#ffd5d4';
  }

  return (
    <CircularProgressbar
      value={percentage}
      text={
        <tspan
          dx={
            Number(percentage) === 100
              ? -28
              : Number(percentage) < 10
              ? -16
              : -20
          }
          dy='8'
          style={{ fontSize: 20, fontFamily: 'SpoqaM' }}
        >
          {percentage}%
        </tspan>
      }
      strokeWidth={18}
      styles={buildStyles({
        strokeLinecap: 'butt',
        textColor: '#212121',
        pathColor: path,
        trailColor: trail,
      })}
    />
  );
};

export default CircleProgressbar;
