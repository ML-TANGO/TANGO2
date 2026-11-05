import React, { useState } from 'react';

import classNames from 'classnames/bind';
import style from './SummaryCsvDownload.module.scss';

const cx = classNames.bind(style);

const SummaryCsvDownload = () => {
  const [profitStatus, setProfitStatus] = useState([
    { label: '전체', value: 'all', isCheck: true },
    { label: 'On-premisis', value: 'onPremises', isCheck: true },
    { label: '퍼블릭 클라우드 전체', value: 'publicCloud', isCheck: true },
  ]);

  const [workspaceStatus, setWorkspaceStatus] = useState([
    { label: '누적 사용 시간', value: 'totalTime', isCheck: true },
    { label: '월 평균 사용 시간', value: 'monthTime', isCheck: true },
    { label: '누적 청구 금액', value: 'totalPay', isCheck: true },
    { label: '월 평균 청구 금액', value: 'monthPay', isCheck: true },
  ]);

  const handleProfitStatus = (value) => {
    setProfitStatus((prevStatus) =>
      prevStatus.map((item) =>
        item.value === value ? { ...item, isCheck: !item.isCheck } : item,
      ),
    );
  };

  const handleWorkspaceStatus = (value) => {
    setWorkspaceStatus((prevStatus) =>
      prevStatus.map((item) =>
        item.value === value ? { ...item, isCheck: !item.isCheck } : item,
      ),
    );
  };

  return (
    <div className={cx('container')}>
      <div className={cx('desc')}>
        다운로드할 데이터를 선택하세요.
        <br />
        선택한 항목들은 CSV 파일로 저장됩니다.
      </div>
      <div className={cx('profit-status')}>
        <span className={cx('title')}>실시간 손익 현황</span>
        <div className={cx('profit-checkbox')}>
          {profitStatus.map(({ label, isCheck, value }) => (
            <div className={cx('value')} key={label}>
              <input
                type='checkbox'
                checked={isCheck}
                onChange={() => handleProfitStatus(value)}
              />
              <span className={cx('label', !isCheck && 'not-select')}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className={cx('workspace-status')}>
        <span className={cx('title')}>워크스페이스별 이용 현황</span>
        <div className={cx('workspace-checkbox')}>
          {workspaceStatus.map(({ label, isCheck, value }) => (
            <div className={cx('value')} key={label}>
              <input
                type='checkbox'
                checked={isCheck}
                onChange={() => handleWorkspaceStatus(value)}
              />
              <span className={cx('label', !isCheck && 'not-select')}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SummaryCsvDownload;
