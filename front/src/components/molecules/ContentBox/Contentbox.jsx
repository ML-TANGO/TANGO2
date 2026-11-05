// CSS Module
import classNames from 'classnames/bind';
import style from './ContentBox.module.scss';
const cx = classNames.bind(style);

function ContentBox({ title, children, customStyle }) {
  return (
    <div className={cx('content-box')} style={customStyle}>
      {title && <p className={cx('title')}>{title}</p>}
      {children}
    </div>
  );
}

export default ContentBox;
