import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { toast } from '@src/components/Toast';

import { callApi, STATUS_SUCCESS } from '@src/network';

import RecordsNav from '../RecordsNav';
import Card from './Card';
import SkeletonCard from './SkeletonCard';

import classNames from 'classnames/bind';
import style from './SummaryTab.module.scss';

const cx = classNames.bind(style);

const SummaryTab = ({ navList }) => {
  const { t } = useTranslation();
  const [wList, setWList] = useState([]);

  const isLoading = useRef(null);
  const getWorkspaceData = useCallback(async () => {
    if (isLoading.current) return;
    isLoading.current = true;

    const response = await callApi({
      url: 'records/summary',
      method: 'get',
    });
    const { result, status, message } = response;
    if (status === STATUS_SUCCESS) {
      setWList(result);
    } else {
      toast.error(message);
    }
    isLoading.current = false;
  }, []);

  useEffect(() => {
    getWorkspaceData();

    const intervalData = setInterval(() => {
      getWorkspaceData();
    }, 1000);

    return () => {
      isLoading.current = null;
      clearInterval(intervalData);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div id='summary-tab'>
      <RecordsNav navList={navList} />
      <div className={cx('list-area')}>
        {isLoading.current === null && (
          <ul className={cx('list')}>
            {[0, 1, 2, 3, 4, 5].map((id) => (
              <SkeletonCard key={id} />
            ))}
          </ul>
        )}
        {!isLoading.current && wList.length === 0 && (
          <div className={cx('no-data')}>{t('noSummary.message')}</div>
        )}
        {!isLoading.current && (
          <ul className={cx('list')}>
            {wList.map((ws, idx) => (
              <Card key={idx} data={ws} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default SummaryTab;
