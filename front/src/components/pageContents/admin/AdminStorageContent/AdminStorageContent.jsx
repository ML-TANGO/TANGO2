import { useCallback, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import Spinner from '@src/components/atoms/Spinner';
import { calPercent } from '@src/components/molecules/CircleGauge/CircleGauge';
import PageHeader from '@src/components/molecules/PageHeader/PageHeader';
import StoragePieChart from '@src/components/pageContents/admin/AdminStorageContent/storageComponent/StoragePieChart/StoragePieChart';

import { openModal } from '@src/store/modules/modal';
import DeferredComponent from '@src/hooks/useDeferredComponent';

// Utils
import { convertBinaryByte } from '@src/utils';

import StorageIndividualItem from './storageComponent/StorageIndividual';
import StorageMainList from './storageComponent/StorageMainList';

import classNames from 'classnames/bind';
import style from './AdminStorageContent.module.scss';

const cx = classNames.bind(style);

const handleOpenAddStorage = (dispatch, clickCount) => {
  if (clickCount < 10) return;
  dispatch(
    openModal({
      modalType: 'ADD_STORAGE',
      modalData: {
        submit: {
          text: 'add.label',
        },
        cancel: {
          text: 'cancel.label',
        },
      },
    }),
  );
};

function AdminStorageContent({
  totalData,
  storageDataList,
  isMountRef,
  isLoadingRef,
}) {
  const dispatch = useDispatch();
  const { t } = useTranslation();

  const [clickCount, setClickCount] = useState(0);
  const handleClickCount = useCallback(() => {
    setClickCount((prev) => prev + 1);
  }, []);

  const handleMoveStorage = useCallback((name) => {
    const element = document.getElementById(name);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  const { total_alloc, total_size, total_used } = totalData;
  const { percentage: mainPercentage } = calPercent(total_size, total_alloc);
  const mainStorageChartLabelList = [
    {
      label: t('total.label'),
      value: convertBinaryByte(total_size),
    },
    {
      label: t('allocateGpu.label'),
      value: convertBinaryByte(total_alloc),
    },
    {
      label: t('storageAvailable.label'),
      value: convertBinaryByte(total_size - total_alloc),
    },
    {
      label: t('enable.label'),
      value: convertBinaryByte(total_used),
    },
  ];

  return (
    <div className={cx('container')}>
      <div
        className={cx('top-header')}
        onClick={() => handleOpenAddStorage(dispatch, clickCount)}
      >
        {/** 스토리지 추가 버튼 전체 스토리지 원 10번 클릭시 활성화 */}
        <PageHeader
          title={t('storage.label')}
          style={{
            marginBottom: '0px',
          }}
        />
      </div>
      <div className={cx('allStorage-cont')}>
        <StoragePieChart
          title={t('totalStorageStatus.label')}
          labelList={mainStorageChartLabelList}
          percentage={mainPercentage}
          handleClickCount={handleClickCount}
        />
        <StorageMainList
          storageDataList={storageDataList}
          handleMoveStorage={handleMoveStorage}
        />
      </div>
      <div className={cx('border')} />
      <div className={cx('individual-storage-list')}>
        <h3 className={cx('individual-title-txt')}>
          {t('individualStorageStatus.label')}
        </h3>
        {storageDataList &&
          storageDataList.length !== 0 &&
          storageDataList.map((info, idx) => {
            const { percentage } = calPercent(total_alloc, total_used);
            const labelList = [
              {
                label: t('allocateGpu.label'),
                value: convertBinaryByte(total_alloc),
              },
              {
                label: t('storageAvailable.label'),
                value: convertBinaryByte(total_alloc - total_used),
              },
              {
                label: t('enable.label'),
                value: convertBinaryByte(total_used),
              },
            ];
            return (
              <div
                id={info.name}
                className={cx('individual-storage-item')}
                key={idx}
              >
                <StoragePieChart
                  title={info.name}
                  percentage={percentage}
                  labelList={labelList}
                  style={{ borderRadius: '16px 0 0 16px' }}
                />
                <StorageIndividualItem
                  title={t('mainStorage.label')}
                  storageList={info.workspaces.main}
                  totalSize={total_size}
                />
                <StorageIndividualItem
                  title={t('dataStorage.label')}
                  storageList={info.workspaces.data}
                  totalSize={total_size}
                  style={{
                    borderRadius: '0 16px 16px 0',
                    borderLeft: 'none',
                  }}
                />
              </div>
            );
          })}
        {storageDataList.length === 0 && (
          <div className={cx('nodata')}>스토리지 리스트가 없습니다.</div>
        )}
      </div>
    </div>
  );
}

export default AdminStorageContent;
