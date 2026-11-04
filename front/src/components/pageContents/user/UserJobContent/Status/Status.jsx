// i18n
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
// CSS module
import style from './Status.module.scss';

const cx = classNames.bind(style);

/**
 * @param {string} status
 * @param {string} title
 * @param {string} type 'light' | 'dark'
 * @param {string} size 'mini | 'medium' | 'large' | 'medium-long'
 * @returns
 */
function Status({
  status,
  title,
  type = 'light',
  size = 'medium',
  onClick,
  customStyle,
}) {
  const { t } = useTranslation();
  return (
    <div
      className={cx('status', status, type, size, title ? 'help' : 'default')}
      title={title}
      onClick={onClick}
      style={customStyle}
    >
      {t(status)}
    </div>
  );
}

export default Status;
