// i18n
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './WorkerListView.module.scss';

const cx = classNames.bind(style);

function WorkerListView({ list, errorMessage }) {
  const { t } = useTranslation();
  const { complete, partial } = list;
  return (
    <div className={cx('worker-list-view')}>
      <div className={cx('list-box')}>
        <div className={cx('list-item')}>
          <div className={cx('message')}>
            {t('deleteWorkerCompletely.message')}
          </div>
          {complete.length > 0 ? (
            <ul className={cx('list')}>
              {complete.map((worker, idx) => (
                <li key={idx}>Worker {worker}</li>
              ))}
            </ul>
          ) : (
            <div className={cx('empty-box')}>No worker</div>
          )}
        </div>
        <div className={cx('middle-line')}></div>
        <div className={cx('list-item')}>
          <div className={cx('message')}>{t('deleteLogPartially.message')}</div>
          {partial.length > 0 ? (
            <ul className={cx('list')}>
              {partial.map((worker, idx) => (
                <li key={idx}>Worker {worker}</li>
              ))}
            </ul>
          ) : (
            <div className={cx('empty-box')}>No worker</div>
          )}
        </div>
      </div>
      {errorMessage && (
        <div className={cx('error-message')}>{errorMessage}</div>
      )}
    </div>
  );
}

export default WorkerListView;
