import classNames from 'classnames/bind';
import style from './DarkTooltip.module.scss';

const cx = classNames.bind(style);

const HiddenTag = ({ tooltipColor }) => {
  return (
    <div className={cx('arrow-hidden')}>
      <svg
        xmlns='http://www.w3.org/2000/svg'
        width='22'
        height='13'
        viewBox='0 0 22 13'
        fill='none'
      >
        <path
          d='M14.4641 17C12.9245 19.6667 9.0755 19.6667 7.5359 17L1.47372 6.49999C-0.0658814 3.83332 1.85862 0.499994 4.93782 0.499995L17.0622 0.499998C20.1414 0.499999 22.0659 3.83333 20.5263 6.5L14.4641 17Z'
          fill={tooltipColor}
        />
      </svg>
    </div>
  );
};

const DarkTooltip = ({
  content,
  direction = 'top',
  tooltipColor = '#042659',
  ...rest
}) => {
  return (
    <div className={cx('tooltip')} {...rest}>
      {direction === 'bottom' && <HiddenTag tooltipColor={tooltipColor} />}
      <div
        className={cx('tooltip-content')}
        style={{ backgroundColor: tooltipColor }}
      >
        {content}
      </div>
      {direction === 'top' && <HiddenTag tooltipColor={tooltipColor} />}
      <div className={cx('svg-cont', direction)}>
        <svg
          xmlns='http://www.w3.org/2000/svg'
          width='22'
          height='19'
          viewBox='0 0 22 19'
          fill='none'
        >
          <path
            d='M14.4641 17C12.9245 19.6667 9.0755 19.6667 7.5359 17L1.47372 6.49999C-0.0658814 3.83332 1.85862 0.499994 4.93782 0.499995L17.0622 0.499998C20.1414 0.499999 22.0659 3.83333 20.5263 6.5L14.4641 17Z'
            fill={tooltipColor}
          />
        </svg>
      </div>
    </div>
  );
};

export default DarkTooltip;
