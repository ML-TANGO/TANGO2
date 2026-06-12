import React from 'react';
import { useTranslation } from 'react-i18next';

import { Badge } from '@tango/ui-react';

import dayjs from 'dayjs';

import DashboardFrame from '../DashboardFrame';
import DashboardPayment from '../DashboardPayment';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardInfo.module.scss';

import EditIcon from '@src/static/images/icon/00-ic-basic-pen.svg';

const cx = classNames.bind(style);

const calStatus = (status, t) => {
  if (status === 'Active')
    return { statusMessage: t('activated.label'), color: 'green' };
  return { statusMessage: t('deactivated.label'), color: 'orange' };
};

const calKorTime = (time) => {
  if (time === '0000-00-00 00:00') return '0000-00-00 00:00';
  return dayjs(time).add(9, 'hour').format('YYYY-MM-DD HH:mm');
};

const DashboardInfo = React.memo(
  ({ name, description, owner, period, status, userParagraph, isManager }) => {
    const { t } = useTranslation();
    const { statusMessage, color } = calStatus(status, t);

    const periodSplit = period.split(' ~ ');
    const startDatetime = calKorTime(periodSplit[0]);
    const endDatetime = calKorTime(periodSplit[1]);

    return (
      <div className={cx('info-wrapper')}>
        <DashboardFrame>
          <div className={cx('info-cont')}>
            <div className={cx('header-cont')}>
              {status && (
                <Badge
                  label={statusMessage}
                  type={color}
                  size='lg'
                  customStyle={{ width: 'fit-content' }}
                />
              )}
              <div className={cx('name-cont')}>
                <span>{name === '-' ? '-' : t('infoOf.label', { name })}</span>
                {isManager && <img src={EditIcon} alt='edit-icon' />}
              </div>
            </div>
            <div className={cx('footer-cont')}>
              <p className={cx('explain-para')}>
                {description.length ? description : '-'}
              </p>
              <div className={cx('border')}></div>
              <div className={cx('detail-info-cont')}>
                <div className={cx('date-cont')}>
                  <span className={cx('label')}>{t('period.label')}</span>
                  <span className={cx('value')}>
                    {startDatetime} ~ {endDatetime}
                  </span>
                </div>
                <div className={cx('user-cont')}>
                  <span className={cx('label')}>{t('user')}</span>
                  <div className={cx('user-right-cont')}>
                    <p className={cx('manager')}>{owner}</p>
                    <div className={cx('users-cont')}>
                      <img
                        src='/images/icon/00-ic-gray-member.svg'
                        alt='user-icon'
                      />
                      <p className={cx('value')}>{userParagraph}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </DashboardFrame>
        <DashboardFrame>
          <DashboardPayment />
        </DashboardFrame>
      </div>
    );
  },
);

export default DashboardInfo;
