import React from 'react';
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './DockerImageLogModalContent.module.scss';

const cx = classNames.bind(style);

const calIsLog = (log) => {
  if (!log) return false;
  return !!log.length;
};

const calLogContent = (log, isLog) => {
  if (!isLog) return '로그가 존재하지 않습니다.';
  const logParagraph = (
    <p className={cx('log-paragraph')}>
      {log.map((el, idx) => (
        <React.Fragment key={idx}>
          {`${el}`}
          <br />
        </React.Fragment>
      ))}
    </p>
  );
  return logParagraph;
};

const DockerImageLogModalContent = ({ log }) => {
  const { t } = useTranslation();

  const isLog = calIsLog(log);
  const logContents = calLogContent(log, isLog);

  return (
    <div className={cx('log-cont')}>
      <span className={cx('log-txt')}>{t('installLog.label')}</span>
      <div className={cx('log-contents', !isLog && 'white')}>
        <div className={cx('scroll-cont')}>{logContents}</div>
      </div>
    </div>
  );
};

export default DockerImageLogModalContent;
