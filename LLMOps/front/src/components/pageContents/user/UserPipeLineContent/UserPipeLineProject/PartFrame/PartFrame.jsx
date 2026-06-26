import React from 'react';
import { shallowEqual, useSelector } from 'react-redux';

// CSS Module
import classNames from 'classnames/bind';
import style from './PartFrame.module.scss';

const cx = classNames.bind(style);

const calSubTitletoTypeList = (
  subTitle,
  preprocessing_task,
  project_task,
  deployment_task,
  generation_task,
  finetuning_task,
  quantize_task,
  llm_deploy_task,
) => {
  if (subTitle === '생성 데이터') return generation_task;
  if (subTitle === '학습 데이터 전처리') return preprocessing_task;
  if (subTitle === '파인튜닝') return finetuning_task;
  if (subTitle === '양자화') return quantize_task;
  if (subTitle === 'LLM 배포') return llm_deploy_task;
  if (subTitle === '학습') return project_task;
  return deployment_task;
};

const calStatusList = (list) => {
  const returnStatusList = list.map((el) => el.status.status);
  return returnStatusList;
};

const calMessage = (subTitle, statusList) => {
  const isPending = statusList.find((el) => el === 'pending');
  const isRunning = statusList.find((el) => el === 'running');

  if (isPending) {
    return {
      color: '#FF7A00',
      message: `${subTitle} 작업 대기 중입니다.`,
    };
  }

  if (isRunning) {
    return {
      color: '#2D76F8',
      message: `${subTitle} 작업 중입니다.`,
    };
  }
  return {
    color: '#747474',
    message: `${subTitle}가 완료되었습니다.`,
  };
};

export default function PartFrame({ subTitle, isStopBtn }) {
  const {
    preprocessing_task,
    project_task,
    deployment_task,
    generation_task,
    finetuning_task,
    quantize_task,
    llm_deploy_task,
  } = useSelector((state) => state.pipelineList, shallowEqual);

  const list = calSubTitletoTypeList(
    subTitle,
    preprocessing_task,
    project_task,
    deployment_task,
    generation_task,
    finetuning_task,
    quantize_task,
    llm_deploy_task,
  );
  const statusList = calStatusList(list);
  const messageValue = calMessage(subTitle, statusList);

  return (
    <section className={cx('frame-cont')}>
      <div className={cx('flex-cont')}>
        <h3 className={cx('sub-title')}>{subTitle}</h3>
        <div className={cx('line')} />
        {isStopBtn && isStopBtn !== 'history' && (
          <div className={cx('message')} style={{ color: messageValue.color }}>
            {messageValue.message}
          </div>
        )}
      </div>
    </section>
  );
}
