import { useTranslation } from 'react-i18next';

import { getKoreaTime } from '@src/datetimeUtils';

import classNames from 'classnames/bind';
import style from './Info.module.scss';

const cx = classNames.bind(style);

export default function Info({ infoData, originGraphData }) {
  const { t } = useTranslation();

  return (
    <div
      className={cx(
        'container',
        originGraphData?.length === 0 ? 'height-528' : 'height-922',
      )}
    >
      <div className={cx('flex-32')}>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>{t('description.label')}</span>
          <span
            className={cx('value', 'desc', !infoData?.description && 'no-desc')}
          >
            {infoData?.description ? infoData?.description : t('no.desc')}
          </span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>{t('accessType.label')}</span>
          <div className={cx('flex-row-8')}>
            {infoData?.access === 0 ? (
              <>
                <span className={cx('label')}>Private</span>
                <span className={cx('value')}>
                  {infoData?.users
                    ?.map(({ user_name: name }) => name)
                    .join(', ')}
                </span>
              </>
            ) : (
              <>
                <span className={cx('label')}>Public</span>
              </>
            )}
          </div>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>{t('owner.label')}</span>
          <span className={cx('value')}>{infoData?.owner ?? '-'}</span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>{t('createdAt.label')}</span>
          <span className={cx('value')}>
            {getKoreaTime(infoData?.create_datetime) ?? '-'}
          </span>
        </div>
        <div className={cx('flex-16')}>
          <span className={cx('label')}>{t('lastUpdatedTime.label')}</span>
          <span className={cx('value')}>
            {getKoreaTime(infoData?.update_datetime) ?? '-'}
          </span>
        </div>
      </div>
    </div>
  );
}
