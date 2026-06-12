// Components
import { Button } from '@tango/ui-react';

// Icon
import download from '@src/static/images/icon/00-ic-data-download-white.svg';

// CSS Module
import classNames from 'classnames/bind';
import style from './SystemLogModal.module.scss';

const cx = classNames.bind(style);

function SystemLogModal({
  workerId,
  head,
  data,
  systemLogLoading,
  systemLogDown,
  downLoading,
  t,
  systemLog,
  traingId,
}) {
  return (
    <div className={cx('wrapper')}>
      <h2 className={cx('title')}>
        {workerId ? `${t('worker')} ${workerId}` : t('training')}
      </h2>
      <div className={cx('head-box')}>
        <div className={cx('head')}>{head}</div>
        {/* <button className={cx('download-btn')}>{t('download.label')}</button> */}
        {traingId && systemLog && (
          <Button
            type='secondary'
            onClick={() => systemLogDown(traingId)}
            loading={downLoading}
            customStyle={{
              backgroundColor: '#DEE9FF',
              color: '#2D76F8',
              border: 'none',
            }}
          >
            {t('download.label')}
          </Button>
        )}
        {workerId && systemLog && (
          <Button
            type='secondary'
            onClick={() => systemLogDown(workerId)}
            loading={downLoading}
            customStyle={{
              backgroundColor: '#DEE9FF',
              color: '#2D76F8',
              border: 'none',
            }}
          >
            {t('download.label')}
          </Button>
        )}
      </div>
      <article className={cx('log-data-box')}>
        {/* {!systemLogLoading ? data : ''} */}
        {!systemLog && (
          <div className={cx('no-data')}>현재 시스템 로그가 없습니다.</div>
        )}

        <pre>{systemLog}</pre>
      </article>
    </div>
  );
}

export default SystemLogModal;
