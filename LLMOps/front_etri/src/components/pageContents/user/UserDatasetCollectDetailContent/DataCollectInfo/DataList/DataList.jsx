import React, { useCallback, useState } from 'react';

import classNames from 'classnames/bind';
import style from './DataList.module.scss';

const cx = classNames.bind(style);

const calInfoData = (jsonData) => {
  if (!jsonData) return [];

  const result = Object.entries(jsonData).map(([key, value]) => ({
    key,
    value,
  }));
  return result;
};

export default function DataList({
  columns = [],
  data = [],
  collect_method,
  ...rest
}) {
  const [isOpen, setOpen] = useState({
    value: false,
    idx: null,
  });
  const handleClick = useCallback(
    (e, idx) => {
      e.stopPropagation();
      if (collect_method !== 'public_api') return;

      setOpen((prev) => ({
        ...prev,
        idx,
        value: prev.idx !== idx ? true : !prev.value,
      }));
    },
    [collect_method],
  );

  return (
    <div className={cx('frame')} {...rest}>
      <div className={cx('table')}>
        <div className={cx('thead')}>
          <h3 className={cx('title')}>수집 데이터 개요</h3>
          <div className={cx('tr')}>
            {columns.map((column, idx) => (
              <div className={cx('th')} key={idx}>
                {column}
              </div>
            ))}
          </div>
        </div>
        <div className={cx('tbody')}>
          {data.map((info, idx) => {
            const { first, second, third, fourth, five, infoData } = info;
            const jsonList = calInfoData(infoData?.jsonData);
            return (
              <React.Fragment key={idx}>
                <div
                  className={cx(
                    'tr',
                    isOpen.value && isOpen.idx === idx && 'open',
                    collect_method === 'public_api' && 'cursor',
                  )}
                  onClick={(e) => handleClick(e, idx)}
                >
                  {first && <div className={cx('td')}>{first}</div>}
                  {second && <div className={cx('td')}>{second}</div>}
                  {third && <div className={cx('td')}>{third}</div>}
                  {fourth && <div className={cx('td')}>{fourth}</div>}
                  {five && (
                    <div className={cx('td')}>
                      <a href={five} target='_blank' rel='noopener noreferrer'>
                        <span>바로가기</span>
                        <img
                          src='/images/icon/00-ic-basic-external-link-grey.svg'
                          alt='link'
                        />
                      </a>
                    </div>
                  )}
                </div>
                {collect_method === 'public_api' &&
                  isOpen.value &&
                  isOpen.idx === idx && (
                    <div className={cx('expand-cont')}>
                      <div className={cx('header-cont')}>
                        <div className={cx('left-cont')}>
                          <span>요청 방식</span>
                          <span>{infoData.method}</span>
                        </div>
                        <div className={cx('right-cont')}>
                          <span>요청 데이터 형식</span>
                          <span>{infoData.data_type ?? 'Params'}</span>
                        </div>
                      </div>
                      <div className={cx('body-cont')}>
                        <span className={cx('params-txt')}>요청변수</span>
                        <div className={cx('table-cont')}>
                          <div className={cx('header-row')}>
                            <span>요청변수 항목명</span>
                            <span>요청변수 값</span>
                          </div>
                          {jsonList.length > 0 &&
                            jsonList.map((i, idx) => (
                              <div className={cx('header-row')} key={idx}>
                                <span>{i.key}</span>
                                {idx !== 0 && <span>{i.value}</span>}
                                {idx === 0 && (
                                  <input
                                    type='password'
                                    value='1234566790'
                                    style={{
                                      width: '100%',
                                      border: 'none',
                                      textAlign: 'center',
                                      backgroundColor: '#fff',
                                    }}
                                    disabled
                                  />
                                )}
                              </div>
                            ))}
                        </div>
                      </div>
                    </div>
                  )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
