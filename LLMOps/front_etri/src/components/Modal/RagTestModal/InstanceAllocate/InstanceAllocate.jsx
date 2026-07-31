import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './InstanceAllocate.module.scss';

const cx = classNames.bind(style);

export default function InstanceAllocate({ listData, columns = [], ...rest }) {
  const { t } = useTranslation();

  return (
    <div className={cx('table')} {...rest}>
      <div className={cx('thead')}>
        <div className={cx('tr')}>
          {columns.map(({ label, headStyle }, key) => (
            <div key={key} className={cx('td')} style={headStyle}>
              {label}
            </div>
          ))}
        </div>
      </div>
      <div className={cx('tbody')}>
        {listData &&
          listData.length > 0 &&
          listData.map((d, idx) => {
            return (
              <div key={idx} className={cx('tr')}>
                {columns.map(({ bodyStyle, selector, cell }, key) => (
                  <div key={key} className={cx('td')} style={bodyStyle}>
                    {cell ? cell(d, idx) : d[selector]}
                  </div>
                ))}
              </div>
            );
          })}
        {listData && listData.length === 0 && (
          <div className={cx('no-data')}>
            <span>{t('noData.message')}</span>
          </div>
        )}
      </div>
    </div>
  );
}
