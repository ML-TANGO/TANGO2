import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './JobStatus.module.scss';

const cx = classNames.bind(style);

const JobStatus = ({ status }) => {
  const { t } = useTranslation();

  const statusClass = status.split('.')[1];

  return <div className={cx('status', statusClass)}>{t(status)}</div>;
};

export default JobStatus;
