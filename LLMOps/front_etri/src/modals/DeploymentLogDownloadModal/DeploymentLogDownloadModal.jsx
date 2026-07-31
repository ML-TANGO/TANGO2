import { useState } from 'react';
import dayjs from 'dayjs';

// i18n
import { useTranslation } from 'react-i18next';

// Custom Hooks
import useLogOptionCheck from './hooks/useLogOptionCheck';

// Components
import DeploymentLogDownloadModalContent from '@src/components/modalContents/DeploymentLogDownloadModalContent/DeploymentLogDownloadModalContent';
import { toast } from '@src/components/Toast';

// Network
import { network } from '@src/network';

// Utils
import { DATE_FORM, today } from '@src/datetimeUtils';
import { defaultSuccessToastMessage } from '@src/utils';

function DeploymentLogDownloadModal({ type, data: modalData }) {
  const { t } = useTranslation();
  const { deploymentId, deploymentName, createDatetime } = modalData;

  const [logOptionState, renderLogOptionCheck] = useLogOptionCheck();
  const [from, setFrom] = useState(dayjs(createDatetime).format(DATE_FORM));
  const [to, setTo] = useState(today(DATE_FORM));
  const [selectedValue, setSelectedValue] = useState('all');

  const isValidate = logOptionState.isValid;

  const rangeSettingOption = [
    {
      label: 'all.label',
      value: 'all',
      labelStyle: {
        marginLeft: '5px',
      },
    },
    {
      label: 'timeRange.label',
      value: 'daterange',
      labelStyle: {
        marginLeft: '5px',
      },
    },
  ];

  const onSubmitDateRange = (from, to) => {
    setFrom(dayjs(from).format(DATE_FORM));
    setTo(dayjs(to).format(DATE_FORM));
  };

  const onRangeSetting = (e) => {
    const { value } = e.currentTarget;
    setSelectedValue(value);
  };

  /**
   * 로그 다운로드
   *
   * @param {string} log 로그
   * @param {string} fileName 파일이름
   */
  const downloadFile = (log, fileName) => {
    const blob = new Blob([log], { type: 'application/tar' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `[LOG]_${fileName}`;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const onSubmit = async (callback) => {
    let query = `deployment_id=${deploymentId}`;

    const { logOptions } = logOptionState;

    if (selectedValue === 'daterange') {
      query = `${query}&start_time=${from} 00:00:00&end_time=${`${to} 23:59:59`}`;
    }
    if (logOptions[0].checked) {
      query = `${query}&nginx_log=True`;
    }
    if (logOptions[1].checked) {
      query = `${query}&api_log=True`;
    }

    const response = await network.callApiWithPromise({
      url: `deployments/download_api_log?${query}`,
      method: 'GET',
    });
    const { data, status, statusText, headers } = response;

    if (status === 200) {
      if (data.status === 0) {
        toast.error(data.message);
      } else {
        let fileName = `${deploymentName}.txt`;
        if (selectedValue === 'daterange') {
          fileName = `${deploymentName}_${from}-${to}.tar`;
        }
        const contentDisposition = headers['content-disposition']; // 파일 이름
        if (contentDisposition) {
          const [fileNameMatch] = contentDisposition
            .split(';')
            .filter((str) => str.includes('filename'));
          if (fileNameMatch) {
            [, fileName] = fileNameMatch.split('=');
          }
        }
        downloadFile(data, fileName);
        defaultSuccessToastMessage('download');
        if (callback) callback();
      }
    } else {
      toast.error(statusText);
    }
  };

  return (
    <DeploymentLogDownloadModalContent
      title={t('logDownload.label')}
      isValidate={isValidate}
      type={type}
      modalData={modalData}
      renderLogOptionCheck={renderLogOptionCheck}
      from={from}
      to={to}
      selectedValue={selectedValue}
      rangeSettingOption={rangeSettingOption}
      onSubmit={onSubmit}
      onSubmitDateRange={onSubmitDateRange}
      onRangeSetting={onRangeSetting}
    />
  );
}

export default DeploymentLogDownloadModal;
