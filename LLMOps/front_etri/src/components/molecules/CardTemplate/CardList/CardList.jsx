import classNames from 'classnames/bind';
import style from './CardList.module.scss';

const cx = classNames.bind(style);

const CardList = ({ children }) => {
  return <div className={cx('card-list')}>{children}</div>;
};

export default CardList;
