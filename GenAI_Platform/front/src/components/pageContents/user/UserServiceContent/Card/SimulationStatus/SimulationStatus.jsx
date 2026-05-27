import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './SimulationStatus.module.scss';

const cx = classNames.bind(style);

function SimulationStatus({ status }) {
  const { t } = useTranslation();

  return (
    <div className={cx('status', status)}>
      {t(status === 'stop' ? 'done' : status)}
    </div>
  );
}

export default SimulationStatus;
