import { ButtonV2 } from '@jonathan/ui-react';

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import PageTitle from '@src/components/atoms/PageTitle';

import {
  handleClosePopup,
  handleOpenPopup,
} from '@src/store/modules/popupState';

import BillingDetailHistory from './BillingDetailHistory';
import DetailCsvDownload from './DetailCsvDownload';
import OperatingCost from './OperatingCost';
import SummaryContent from './SummaryContent';
import SummaryCsvDownload from './SummaryCsvDownload';

import classNames from 'classnames/bind';
import style from './AdminBillingMonitoring.module.scss';

const cx = classNames.bind(style);

const AdminBillingMonitoringContent = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [tab, setTab] = useState('summary');
  const tabInfo = [
    { label: 'summary.label', value: 'summary' },
    { label: 'cost.label', value: 'cost' },
    { label: 'detail.label', value: 'detail' },
  ];

  const openCsvDownloadPopup = () => {
    dispatch(
      handleOpenPopup({
        type: 'main',
        isAnimation: true,
        popupTitle: 'csv 다운로드',
        popupContents:
          tab === 'summary' ? <SummaryCsvDownload /> : <DetailCsvDownload />,
        submitBtnLabel: t('download.label'),
        cancelBtnLabel: t('cancel.label'),
        handleSubmit: () => {
          dispatch(handleClosePopup());
        },
        handleCancel: () => {},
        style: {
          width: '456px',
        },
      }),
    );
  };

  const rightComponent = (
    <ButtonV2
      label={`csv ${t('download.label')}`}
      size='l'
      colorType='skyblue'
      onClick={openCsvDownloadPopup}
    />
  );

  return (
    <div className={cx('container')}>
      <div className={cx('page-header-cont')}>
        <PageTitle>{t('Monitoring')}</PageTitle>
        <div className={cx('right-cont')}>
          {tab !== 'cost' && rightComponent}
        </div>
      </div>
      <div className={cx('tab-container')}>
        {tabInfo.map(({ label, value }) => (
          <span
            className={cx('tab', tab === value && 'selected')}
            onClick={() => setTab(value)}
            key={label}
          >
            {t(label)}
          </span>
        ))}
      </div>
      <div className={cx('gray-line')}></div>
      {tab === 'summary' && <SummaryContent />}
      {tab === 'detail' && <BillingDetailHistory />}
      {tab === 'cost' && <OperatingCost />}
    </div>
  );
};

export default AdminBillingMonitoringContent;
