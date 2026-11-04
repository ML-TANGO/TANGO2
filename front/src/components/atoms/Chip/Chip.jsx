// CSS module
import classNames from 'classnames/bind';
import style from './Chip.module.scss';
const cx = classNames.bind(style);

const Chip = ({ label, onClick = () => {} }) => {
  return (
    <span className={cx('chip')}>
      {label}
      <button onClick={onClick} className={cx('remove-btn')}>
        <img src='/images/icon/close-s.svg' alt='x' />
      </button>
    </span>
  );
};

export default Chip;
