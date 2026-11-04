// i18n

// Icon
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { Button } from '@jonathan/ui-react';

import Status from '@src/components/atoms/Status';
import AccuracyLossChart from '@src/components/molecules/chart/AccuracyLossChart';

import { closeModal, openModal } from '@src/store/modules/modal';
import useIntervalCall from '@src/hooks/useIntervalCall';

// Custom Hooks

// Components
import ModalFrame from '../ModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './JobLogModal.module.scss';

const cx = classNames.bind(style);

const JobLogModal = ({
  validate,
  data,
  type,
  logData,
  totalLength,
  jobName,
  jobData,
  jobStatus,
  downloadLog,
  metricsData,
  metricsInfo,
  parameterSettings,
  onSubmit,
  guideLodResult,
  getJobLog,
}) => {
  const dispatch = useDispatch();
  const { t } = useTranslation();
  const [isGuideLogShow, setIsGuideLogShow] = useState(false);
  const { submit, trainingName } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const handleGuideModal = useCallback(() => {
    dispatch(
      openModal({
        modalType: 'VISUALIZATION_GUIDE',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('VISUALIZATION_GUIDE'));
            },
          },
        },
      }),
    );
  }, [dispatch]);

  // 1초마다 api 호출하는게 학습 결과 시각화 가이드 모달을 닫을때
  // 학습 결과 모달이 닫히는 사이드 이팩트를 일으킴!!
  // useIntervalCall(getJobLog, 1000);

  useEffect(() => {
    getJobLog();
  }, []);

  return (
    <ModalFrame
      submit={newSubmit}
      type={type}
      validate={validate}
      isResize={true}
      isMinimize={true}
      title={`[${trainingName}] ${t('trainingResultOf.label', {
        name: `${jobName}`,
      })}`}
      customStyle={{
        width: '1000px',
      }}
    >
      <h2 className={cx('title')}>
        <Status status={jobStatus.status} />
        {`[${trainingName}] ${t('trainingResultOf.label', {
          name: `${jobName}`,
        })}`}
      </h2>
      <div className={cx('form')}>
        <div className={cx('parameter-box')}>
          <h3 className={cx('sub-title')}>{t('parameterSettings.label')}</h3>
          <div className={cx('parameter')}>
            {parameterSettings.length > 0
              ? parameterSettings.map(({ key, value }, idx) => (
                  <div key={idx}>
                    <label className={cx('label')}>{key}</label>
                    <span className={cx('value')}>{value}</span>
                  </div>
                ))
              : '-'}
          </div>
        </div>
        <div className={cx('chart')}>
          <h3 className={cx('sub-title')}>
            <span>{t('graph.label')}</span>
            <div className={cx('flex-cont')}>
              {(!metricsInfo.keyOrder || metricsInfo.length <= 0) && (
                <div className={cx('btn')} onClick={handleGuideModal}>
                  {t('visualizationGuide.label')}
                </div>
              )}
            </div>
          </h3>
          <AccuracyLossChart
            data={metricsData}
            info={metricsInfo}
            width={904}
            height={337}
          />
        </div>
        <div className={cx('line')}></div>
        <div className={cx('log')}>
          <h3 className={cx('sub-title')}>{t('log.label')}</h3>
          <Button
            type='secondary'
            onClick={() => downloadLog(jobData.index + 1)}
            customStyle={{
              padding: '10px 16px',
              width: '113px',
              height: '32px',
              border: '1px solid #dee9ff',
              borderRadius: '4px',
              color: '#2D76F8',
              backgroundColor: '#dee9ff',
              fontSize: '14px',
              fontWeight: 700,
            }}
          >
            {t('logDownload.label')}
          </Button>
        </div>
        <div className={cx('row')}>
          {(() => {
            const arr = [];
            for (let i = 0; i < logData.length; i += 1) {
              if (totalLength > 200 && i === 100) {
                arr.push(
                  <p key='ellipsis' className={cx('ellipsis')}>
                    .<br />.<br />.<br />
                  </p>,
                );
              }
              if (logData[i].length === 0) {
                arr.push(<br key={i} />);
              } else {
                arr.push(<p key={i}>{logData[i]}</p>);
              }
            }
            return arr;
          })()}
        </div>
      </div>
    </ModalFrame>
  );
};

export default JobLogModal;
