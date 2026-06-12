import classNames from 'classnames/bind';
import style from './CommitListDetail.module.scss';

const cx = classNames.bind(style);

function CommitListDetail({ data, t }) {
  return (
    <div className={cx('container')}>
      <div className={cx('title')}>{data?.name ?? '-'}</div>
      <div className={cx('bar')}></div>
      <div className={cx('content', 'top')}>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('commitMessage.label')}</div>
          <div className={cx('value')}>
            {(data?.commit_message ?? '').trim() === ''
              ? '-'
              : data.commit_message}
          </div>
        </div>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('writer.label')}</div>
          <div className={cx('value')}>{data?.create_user_name ?? '-'}</div>
        </div>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('commitDate.label')}</div>
          <div className={cx('value')}>{data?.commit_datetime ?? '-'}</div>
        </div>
      </div>
      <div className={cx('content', 'bottom')}>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('modelDescription.label')}</div>
          <div className={cx('value')}>
            {(data?.model_description ?? '').trim() === ''
              ? '-'
              : data.model_description}
          </div>
        </div>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('creator.label')}</div>
          <div className={cx('value')}>{t('create_user_name')}</div>
        </div>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('createdDatetime.label')}</div>
          <div className={cx('value')}>{data?.commit_datetime ?? '-'}</div>
        </div>
        <div className={cx('card')}>
          <div className={cx('col')}>{t('lastUpdatedTime.label')}</div>
          <div className={cx('value')}>{data?.commit_datetime ?? '-'}</div>
        </div>
      </div>
    </div>
  );
}

export default CommitListDetail;
