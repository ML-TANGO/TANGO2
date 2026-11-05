// CSS module
import { convertLocalTime } from '@src/datetimeUtils';
import { useTranslation } from 'react-i18next';

import { capitalizeFirstLetter } from '@src/utils';

import classNames from 'classnames/bind';
import style from './UserTestContentHeader.module.scss';

const cx = classNames.bind(style);

const UserTestContentHeader = ({ info }) => {
  const {
    type,
    name,
    description,
    built_in_model_name: builtInModelName,
    creator,
    date,
  } = info;
  const { t } = useTranslation();
  return (
    <div className={cx('info-box')}>
      <div className={cx('left')}>
        <div className={cx('left-content')}>
          <img src='/images/icon/ic-00-simulation.svg' alt='icon' />

          <label className={cx('service-title')}>{name}</label>
        </div>

        {/* <div className={cx('meta')}>
          <label>{t('modelName.label')}</label>
          <span>{builtInModelName || '-'}</span>
        </div> */}
      </div>

      <div className={cx('right')}>
        <div className={cx('service-description')}>
          {description
            ? description
                .trim()
                .split('\n')
                .map((line, index) => {
                  return (
                    <span key={index}>
                      {line}
                      <br />
                    </span>
                  );
                })
            : '-'}
        </div>
        <div className={cx('service-info')}>
          <div className={cx('meta')}>
            <div className={cx('label')}>{t('updatedAt.label')}</div>
            <div className={cx('value')}>{convertLocalTime(date)}</div>
          </div>
          <div className={cx('meta')}>
            <div className={cx('label')}>{t('creator.label')}</div>
            <div className={cx('value')}>{creator || '-'}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserTestContentHeader;
