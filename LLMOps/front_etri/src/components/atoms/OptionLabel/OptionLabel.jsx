// CSS module
import classNames from 'classnames/bind';
import style from './OptionLabel.module.scss';
const cx = classNames.bind(style);

const OptionLabel = ({ children, borderColor, textColor, width }) => {
  return (
    <span
      className={cx('label')}
      style={{ color: textColor, borderColor, width }}
    >
      {children}
    </span>
  );
};

export default OptionLabel;
