import { Loading } from '@jonathan/ui-react';

import WarningIcon from '@src/static/images/icon/ic-warning-yellow.svg';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { addNineHours, formatSecondsToDHMS, getElapsedTime } from '@src/utils';

import BasicLineChart from './BasicLineChart';

import classNames from 'classnames/bind';
import style from './FineTuningGraph.module.scss';

const cx = classNames.bind(style);

const initialStatus = {
  commit_status: {
    status: null,
    type: null,
    reason: null,
  },
  fine_tuning_status: {
    status: null,
    reason: null,
  },
};

const initialProgressData = {
  percent: 0,
  remaining_time: null,
  start_datetime: null,
  total_epoch: null,
};

// ** header 메시지 출력
const isCalMessage = (
  commit,
  finetuning,
  datasetList,
  configList,
  fineTuningType,
) => {
  const { status: commitStatus, type: commitType } = commit;
  const { status: finetuningStatus } = finetuning;

  if (!finetuningStatus || !commitStatus) return { message: '', color: '' };
  if (finetuningStatus === 'stop') {
    if (datasetList.length === 0) {
      return { message: 'fineTuningUpload.message', color: '' };
    }
    if (fineTuningType === 2) {
      if (configList.length === 0)
        return { message: 'finetuning.config.warn.message', color: '' };
    }
    return { message: 'fineTuningStop.message', color: '' };
  }

  return { message: 'fineTuningNoGraph.message', color: '' };
};

// ** 그래프 데이터 있는지 체크
const canRenderGraphData = (
  fineTuningStatus,
  fineStatus,
  isObjectNull,
  data,
) => {
  if (fineTuningStatus.status && fineStatus && !isObjectNull && data) {
    return true;
  }
  return false;
};

// ** Time 데이터 표시 체크
const canRenderTime = (fineTuningStatus, fineStatus, isObjectNull, data) => {
  if (
    fineTuningStatus.status &&
    fineTuningStatus.status === 'running' &&
    fineStatus &&
    !isObjectNull &&
    data
  ) {
    return true;
  }
  return false;
};

function isCalObjectNull(data) {
  return data && typeof data === 'object' && Object.keys(data).length === 0;
}

function FineTuningGraph({
  data,
  fineStatus,
  fineTuningData,
  progressData,
  fineTuningType,
}) {
  // fineTuningType 1  / 2
  const {
    steps_per_epoch: stepsPerEpoch,
    model_datasets: datasetList,
    model_config_file_list: configList,
  } = fineTuningData || {
    steps_per_epoch: 0,
    model_datasets: [],
    model_config_file_list: [],
  };

  const {
    percent,
    remaining_time: remainingTime,
    start_datetime: startDatetime,
  } = progressData ?? initialProgressData;

  const { commit_status: commitStatus, fine_tuning_status: finetuningStatus } =
    fineStatus ?? initialStatus;

  const { t } = useTranslation();

  const isErrorState = useMemo(() => {
    return (
      finetuningStatus.status === 'error' ||
      (finetuningStatus.status === 'done' && isCalObjectNull(data))
    );
  }, [finetuningStatus, data]);

  const { message, color } = isCalMessage(
    commitStatus,
    finetuningStatus,
    datasetList,
    configList,
    fineTuningType,
  );

  const isObjectNull = isCalObjectNull(data);

  const statusMessage = () => {
    // const { status: graphStatus } = status || {};
    // if (isErrorState) return;
    // if (graphStatus === 'stop') {
    //   return t('fineTuningStop.message');
    // }

    return t('fineTuningNoGraph.message');
  };

  const renderStatusContent = () => {
    const { status: graphStatus } = finetuningStatus || {};

    if (!finetuningStatus || !fineStatus) {
      return (
        <div className={cx('loading')}>
          <Loading />
        </div>
      );
    }

    if (
      finetuningStatus.status === 'pending' ||
      finetuningStatus.status === 'installing'
    ) {
      return (
        <div className={cx('pending-container')}>
          {t('fineTuningPending.message')}
        </div>
      );
    }

    if (isErrorState) {
      return (
        <div className={cx('error-container')}>
          <img
            src={WarningIcon}
            alt=''
            style={{ width: '16px', height: '16px' }}
          />
          {t('finetuning.error.message')}
        </div>
      );
    }
    if (graphStatus === 'stop') {
      return <div className={cx('no-data')}>{t('fineTuningStop.message')}</div>;
    }
    return (
      <div className={cx('no-data')}>{t('fineTuningNoGraph.message')}</div>
    );

    // 기본 또는 알 수 없는 상태 처리
    // return null;
  };

  const isGraphDataReady = canRenderGraphData(
    finetuningStatus,
    fineStatus,
    isObjectNull,
    data,
  );

  const isTimeDataReady = canRenderTime(
    finetuningStatus,
    fineStatus,
    isObjectNull,
    data,
  );

  return (
    <div
      className={cx(
        'container',
        isErrorState && 'error',
        isGraphDataReady && 'running',
        !isTimeDataReady && 'padding-24',
      )}
    >
      {isTimeDataReady && (
        <div className={cx('time-message')}>
          <div className={cx('percent')}>
            {t('progress.current.label')}: {percent ? Math.floor(percent) : 0}%
          </div>
          <div className={cx('time')}>
            {t('elapsedTime.label')}{' '}
            {getElapsedTime(addNineHours(startDatetime))}
          </div>
          {remainingTime && (
            <div className={cx('time')}>
              {t('timeRemaining.label')} {formatSecondsToDHMS(remainingTime)}
            </div>
          )}
        </div>
      )}
      {!data && ( // 초기에 데이터 없는 경우
        <div className={cx('loading')}>
          <Loading />
        </div>
      )}

      {(!finetuningStatus.status || isObjectNull) && ( // 데이터는 있으나 그래프 없는 경우
        <div className={cx('message')} style={{ color }}>
          {t(message)}
        </div>
      )}

      {isGraphDataReady && // 데이터도 있고 그래프도 있음
        Object.keys(data).length > 0 && (
          <div className={cx('graph-box')}>
            {Object.entries(data).map(([key, value]) => (
              <BasicLineChart
                key={key}
                title={key}
                steps={value.steps}
                // steps={value.steps}
                values={value.values}
                stepsPerEpoch={stepsPerEpoch}
              />
            ))}
          </div>
        )}
    </div>
  );
}

export default FineTuningGraph;
