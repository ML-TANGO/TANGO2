// i18n
import { useTranslation } from 'react-i18next';

// CSS module
import style from './Status.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

/**
 * @param {string} status
 * @param {string} title
 * @param {string} type 'light' | 'dark'
 * @param {string} size 'mini | 'medium' | 'large' | 'medium-long'
 * @returns
 */
function Status({ status, title, type = 'light', size = 'medium', onClick }) {
  const { t } = useTranslation();
  return (
    <div
      className={cx('status', status, type, size, title ? 'help' : 'default')}
      title={title}
      onClick={onClick}
    >
      {t(status)}
    </div>
  );
}

export default Status;
