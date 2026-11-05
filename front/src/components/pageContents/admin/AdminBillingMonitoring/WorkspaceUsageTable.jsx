import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import GrayDropDown from '@src/components/Modal/BasicFeeOptionModal/GrayDropDown';

import ExpandRow from './ExpandRow';

import classNames from 'classnames/bind';
import style from './WorkspaceUsageTable.module.scss';

const cx = classNames.bind(style);

const WorkspaceUsageTable = () => {
  const { t } = useTranslation();
  const [expandList, setExpandList] = useState([]);
  const [sortType, setSortType] = useState({
    label: '누적 사용 시간',
    value: 'total_time',
  });

  const [mockData, setMockData] = useState([
    {
      name: '워크스페이스 1',
      manager: 'david',
      type: ['종량제, 구독제', '구독제'],
      total_time: '913 hr 39 m 39 s',
      month_time: '913 hr 39 m 39 s',
      total_fee: 90000,
      month_fee: 80000,
      current_member: 10,
      add_member: 5,
    },
    {
      name: '워크스페이스 2',
      manager: 'kim',
      type: ['구독제', '구독제'],
      total_time: '100 hr 29 m 19 s',
      month_time: '103 hr 01 m 31 s',
      total_fee: 20000,
      month_fee: 30000,
      current_member: 10,
      add_member: 5,
    },
    {
      name: '워크스페이스 3',
      manager: 'park',
      type: ['종량제', '종량제'],
      total_time: '90 hr 09 m 11 s',
      month_time: '113 hr 18 m 39 s',
      total_fee: 40000,
      month_fee: 50000,
      current_member: 10,
      add_member: 5,
    },
    {
      name: '워크스페이스 4',
      manager: 'jeon',
      type: ['종량제, 구독제', '구독제'],
      total_time: '13 hr 00 m 01 s',
      month_time: '945 hr 17 m 45 s',
      total_fee: 12000,
      month_fee: 45000,
      current_member: 10,
      add_member: 5,
    },
  ]);

  const tableColumn = [
    { label: t('workspaceName.label'), style: { flex: 2 } },
    { label: t('plan.type.label'), style: { flex: 2.5 } },
    { label: t('recordTime.label'), style: { flex: 1.5 } },
    { label: t('month.time.label'), style: { flex: 1.5 } },
    { label: t('currentMemberCount'), style: { flex: 1 } },
    { label: t('addMemberCount'), style: { flex: 1 } },
    { label: t('total.fee.label'), style: { flex: 1 } },
    { label: t('month.fee.label'), style: { flex: 1 } },
  ];

  const sortTypeList = [
    { label: '누적 사용 시간', value: 'total_time' },
    {
      label: '월 평균 사용 시간',
      value: 'average_time',
    },
    {
      label: '누적 청구 금액',
      value: 'total_cost',
    },
    {
      label: '월 평균 청구 금액',
      value: 'average_cost',
    },
  ];

  const handleSortType = ({ label, value }) => {
    setSortType({ label, value });
  };

  const handleExapndList = (index) => {
    setExpandList((prev) => prev.map((v, i) => (i === index ? !v : v)));
  };

  useEffect(() => {
    setExpandList([...Array(4).fill(false)]);
  }, []);

  return (
    <div className={cx('table-container')}>
      <div className={cx('table-header')}>
        <div className={cx('title')}>워크스페이스별 이용 현황</div>
        <div className={cx('sort-box')}>
          <span>정렬기준</span>
          <GrayDropDown
            list={sortTypeList}
            value={sortType}
            placeholder={t('누적 사용 시간')}
            handleSelectOption={handleSortType}
            customStyle={{ width: '200px' }}
            isCloseBorder={false}
          />
        </div>
      </div>
      <div className={cx('table-column')}>
        {tableColumn.map(({ label, style }) => (
          <div className={cx('column')} key={label} style={{ ...style }}>
            {label}
          </div>
        ))}
      </div>
      <div className={cx('table-row')}>
        {mockData.map(
          (
            {
              name,
              manager,
              type,
              total_fee,
              total_time,
              month_fee,
              month_time,
              current_member,
              add_member,
            },
            index,
          ) => (
            <div className={cx('row-box')} key={index}>
              <div
                className={cx('row-data')}
                onClick={() => handleExapndList(index)}
              >
                <div className={cx('data')}>
                  <div className={cx('order')}>{index + 1}</div>
                  <span>{name}</span>
                  <span className={cx('manager')}>{manager}</span>
                </div>
                <div className={cx('data')}>
                  <span className={cx('type')}>인스턴스</span>
                  <span className={cx('type-value')}>{type[0]}</span>
                  <span className={cx('type')}>스토리지</span>
                  <span className={cx('type-value')}>{type[1]}</span>
                </div>
                <div className={cx('data')}>{total_time}</div>
                <div className={cx('data')}>{month_time}</div>
                <div className={cx('data')}>{current_member}</div>
                <div className={cx('data')}>{add_member}</div>
                <div className={cx('data')}>
                  {total_fee.toLocaleString()} 원
                </div>
                <div className={cx('data')}>
                  {month_fee.toLocaleString()} 원
                </div>
              </div>
              {expandList[index] && (
                <ExpandRow
                  name={name}
                  manager={manager}
                  total_fee={total_fee}
                  total_time={total_fee}
                  month_fee={month_fee}
                  month_time={month_time}
                />
              )}
            </div>
          ),
        )}
      </div>
    </div>
  );
};

export default WorkspaceUsageTable;
