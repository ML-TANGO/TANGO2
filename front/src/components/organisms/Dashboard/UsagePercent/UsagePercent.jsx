import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';

// i18n
import { withTranslation } from 'react-i18next';

// CSS module
import style from './UsagePercent.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const UsagePercent = ({ name, total, used, type, t }) => {
  let percentage = 0;
  if (Number(total) !== 0) {
    percentage = ((Number(used) / Number(total)) * 100).toFixed(0);
  }
  if (total === '-') {
    percentage = '';
  }

  let path = '';
  let trail = '';
  if (percentage === '') {
    path = '#c1c1c1';
    trail = '#dbdbdb';
  } else if (percentage <= 25) {
    path = '#00c775';
    trail = '#e3fcee';
  } else if (percentage <= 50) {
    path = '#ffc500';
    trail = '#fff8d9';
  } else {
    path = '#fa4e57';
    trail = '#ffe6e5';
  }

  return (
    <div className={cx('usage-chart', type)}>
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
            {percentage}
            {percentage !== '' && '%'}
          </tspan>
        }
        strokeWidth={18}
        styles={buildStyles({
          strokeLinecap: 'butt',
          textColor: '#121619',
          pathColor: path,
          trailColor: trail,
        })}
      />
      <label className={cx('name')}>{t(name)}</label>
      <div className={cx('usage')}>
        {`${used}/${total}`}
        {used > total && <img src='/images/icon/error-o.svg' alt='deleted' />}
        {name === 'storage.label' && (
          <span className={cx('unit')}>{percentage !== '' && 'GB'}</span>
        )}
      </div>
    </div>
  );
};

export default withTranslation()(UsagePercent);
