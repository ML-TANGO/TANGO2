import React from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './CollectMethodList.module.scss';

const cx = classNames.bind(style);

// @ts-check
export default function CollectMethodList({
  title,
  collectMethodColumn,
  collectMethodList,
  handleMethodModal,
  handleModify,
  ...rest
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('row')}>
      <div className={cx('header')}>
        <h3 className={cx('header-title')}>{title}</h3>
        {title !== '추가된 API 데이터 목록' && (
          <ButtonV2 onClick={handleMethodModal}>추가</ButtonV2>
        )}
      </div>
      <div className={cx('table')} {...rest}>
        <div className={cx('thead')}>
          <div className={cx('tr')}>
            {collectMethodColumn.map(({ label, headStyle }, key) => (
              <div key={key} className={cx('td')} style={headStyle}>
                {label}
              </div>
            ))}
          </div>
        </div>
        <div className={cx('tbody')}>
          {collectMethodList &&
            collectMethodList.length > 0 &&
            collectMethodList.map((d, idx) => {
              return (
                <div key={idx} className={cx('tr')}>
                  {collectMethodColumn.map(
                    ({ bodyStyle, selector, cell }, key) => (
                      <div key={key} className={cx('td')} style={bodyStyle}>
                        {cell ? cell(d, idx) : d[selector]}
                      </div>
                    ),
                  )}
                </div>
              );
            })}
          {collectMethodList.length === 0 && (
            <div className={cx('no-data')}>
              <span>{t('noData.message')}</span>
            </div>
          )}
        </div>
      </div>
      {title === '추가된 API 데이터 목록' && (
        <div className={cx('component-btn')}>
          <ButtonV2
            label={'Custom API 추가'}
            onClick={handleMethodModal}
            style={{ marginTop: '8px' }}
          />
        </div>
      )}
    </div>
  );
}
