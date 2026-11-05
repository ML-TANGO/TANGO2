// CSS module
import classNames from 'classnames/bind';
import style from './ToBeUpdatedBox.module.scss';
const cx = classNames.bind(style);

const ToBeUpdatedBox = () => {
  return (
    <div className={cx('box')}>
      <p className={cx('text')}>To be updated</p>
    </div>
  );
};

export default ToBeUpdatedBox;
