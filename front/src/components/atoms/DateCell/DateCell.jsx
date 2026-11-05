// CSS module
import classNames from 'classnames/bind';
import style from './DateCell.module.scss';
const cx = classNames.bind(style);

const DateCell = ({ gpuTotal, gpuFreeMap, d, propItem }) => {
  const { selected, from, to, disabled, thisMonth, onClick } = propItem;
  const date = d.format('YYYY-MM-DD');
  let count = gpuFreeMap[date];
  if (count < 0) count = 0;
  let status = '';
  const rate = (count / gpuTotal) * 100;
  if (rate <= 30) {
    status = 'red';
  } else if (rate > 30 && rate <= 60) {
    status = 'yellow';
  } else if (rate <= 100) {
    status = 'lime';
  }
  return (
    <span
      className={cx(
        'cell',
        selected && 'selected',
        from && 'from',
        to && 'to',
        disabled && 'disabled',
        thisMonth && 'this-month',
      )}
      onClick={onClick}
    >
      <span className={cx('inner-cell')}>
        <span className={cx('date')}>{d.date()}</span>
        {/* {thisMonth && !disabled && (
          <span
            className={cx('count', count === undefined && 'loading', status)}
          >
            {count < 0 ? 0 : count}
          </span>
        )} */}
      </span>
    </span>
  );
};

export default DateCell;
