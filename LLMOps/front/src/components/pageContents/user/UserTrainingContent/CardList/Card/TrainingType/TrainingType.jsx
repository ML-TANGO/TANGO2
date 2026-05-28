// CSS Module
import classNames from 'classnames/bind';
import style from './TrainingType.module.scss';
const cx = classNames.bind(style);

function TrainingType({ type }) {
  return (
    <div className={cx('type')}>
      <img
        className={cx('type-icon')}
        src={`/images/icon/00-ic-data-${type}-yellow.svg`}
        alt={type}
      />
      <span className={cx('type-label')}>
        {type === 'jupyter' ? 'Jupyter Notebook' : type}
        {/* : capitalizeFirstLetter(type) || '-'} */}
      </span>
    </div>
  );
}

export default TrainingType;
