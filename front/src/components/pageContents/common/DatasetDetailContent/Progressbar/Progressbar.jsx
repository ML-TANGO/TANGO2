import {
  InputNumber,
  InputText,
  Radio as JonathanRadio,
  Selectbox,
  Tooltip,
} from '@jonathan/ui-react';

import PropTypes from 'prop-types';
import { memo, useEffect, useRef } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './Progressbar.module.scss';

const cx = classNames.bind(style);

const Progressbar = memo(
  ({
    value,
    color,
    height,
    pending,
    pendingSpeed = 'first',
    className,
    noFullColor = false,
    isFlow = false,
    pcent = 0,
    remainTime = 0,
    totalSize,
    uploadSize,
    status,
    fake,
  }) => {
    const { t } = useTranslation();
    const progressRef = useRef(null);
    const progressFlowRef = useRef(null);

    const formatTime = (seconds) => {
      if (typeof value !== 'number') {
        return t('calculating.label');
      }
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const remainingSeconds = seconds % 60;

      const hoursString = hours > 0 ? `${hours}${t('time.label')}` : '';
      const minutesString = minutes > 0 ? `${minutes}${t('minute.label')}` : '';
      const secondsString =
        remainingSeconds > 0 ? `${remainingSeconds}${t('second.label')}` : '';

      return `${hoursString} ${minutesString} ${secondsString}`.trim();
    };

    const moveProgress = () => {
      if (progressRef.current) {
        progressRef.current.style.height = `${height}px`;
        progressRef.current.style.width = `${value}%`;
        if (color) {
          progressRef.current.style.backgroundColor = color;
        }
      }
      if (progressFlowRef.current) {
        progressFlowRef.current.style.width = `${value}%`;
      }
    };

    useEffect(() => {
      moveProgress();
    }, [height, value, color, pending]);

    return (
      <>
        <div className={cx('box')}>
          <div className={cx('box-content')}>
            <div className={cx('text-wrapper')}>
              <span className={cx('text-progress')}>
                <span className={cx('title')}>{t('progress.label')}</span>
                <span className={cx('value')}>{value}</span>
                <span className={cx('pcent')}> %</span>
              </span>
              <span className={cx('text-time')}>
                <span className={cx('title')}>{t('remainingTime.label')}</span>
                <span className={cx('value')}>
                  {fake
                    ? `${t('calculating.label')}...`
                    : formatTime(remainTime)}
                </span>
              </span>
            </div>
            <div className={cx('progress-bar', className)}>
              <span
                className={cx(pending && 'loading-bar', 'bar', pendingSpeed)}
              >
                <div
                  className={cx(
                    pending && 'progress-pending',
                    'progress',
                    !noFullColor && value >= 100 && 'full',
                    status === 'error' && 'error',
                  )}
                  ref={progressFlowRef}
                >
                  <span ref={progressRef}></span>
                  {isFlow && <div className={cx('progress-flow-bar')}></div>}
                </div>
              </span>
            </div>
            <div className={cx('remaining')}>
              {/* {`${value}` === '0' ? `-` : `${uploadSize}/${totalSize}`} */}
              {typeof value === 'number' ? `${uploadSize}/${totalSize}` : '-'}
            </div>
          </div>
        </div>
      </>
    );
  },
);

Progressbar.propTypes = {
  value: PropTypes.number.isRequired,
  color: PropTypes.string,
  height: PropTypes.number,
  pending: PropTypes.bool,
  pendingSpeed: PropTypes.oneOf(['first', 'second', 'third']),
  className: PropTypes.string,
  noFullColor: PropTypes.bool,
  isFlow: PropTypes.bool,
};

export default Progressbar;
