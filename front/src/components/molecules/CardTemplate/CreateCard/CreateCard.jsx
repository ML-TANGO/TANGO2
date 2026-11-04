import classNames from 'classnames/bind';
import style from './CreateCard.module.scss';

const cx = classNames.bind(style);

function CreateCard({ label, handleCreateCard, width, minWidth, height }) {
  return (
    <button
      className={cx('create-card')}
      data-testid='open-create-training-modal-btn'
      onClick={handleCreateCard}
      style={{ width, minWidth, height }}
      aria-label={`${label} 버튼`}
    >
      <div className={cx('inner-box')}>
        <div className={cx('plus')}></div>
        <span className={cx('text')}>{label}</span>
      </div>
    </button>
  );
}

export default CreateCard;
