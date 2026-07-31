// CSS module
import classNames from 'classnames/bind';
import style from './Bullet.module.scss';
const cx = classNames.bind(style);

const Bullet = ({ text, status }) => {
  return (
    <span className={cx('box')}>
      <span className={cx('bullet', status)}></span>
      {text}
    </span>
  );
};

export default Bullet;
