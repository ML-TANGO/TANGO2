// CSS Module
import classNames from 'classnames/bind';
import style from './CircleLoading.module.scss';
const cx = classNames.bind(style);

const CircleLoading = ({ size = 'small' }) => {
  return <div className={cx('loading', size)}></div>;
};

export default CircleLoading;
