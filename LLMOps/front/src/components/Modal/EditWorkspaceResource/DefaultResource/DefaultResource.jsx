import { useTranslation } from 'react-i18next';

import RangeBar from '../RangeBar';

import classNames from 'classnames/bind';
import style from './DefaultResource.module.scss';

const cx = classNames.bind(style);

const DefaultResource = ({ range, maxRange, handleRangeBar }) => {
  const { t } = useTranslation();

  return (
    <div className={cx('cont')}>
      <div className={cx('first-header-cont')}>
        {t('learningResourceManagement.label')}
      </div>
      <div className={cx('first-body-cont')}>
        <p className={cx('title')}>{t('learningToolLimit.label')}</p>
        <div className={cx('flex-row')}>
          <RangeBar
            label={'CPU Cores'}
            setting={'learningToolCpu'}
            range={range}
            handleRangeBar={handleRangeBar}
            max={maxRange.cpu}
            step={1}
            unit={t('eaOnly.label')}
          />
          <RangeBar
            label={'RAM'}
            setting={'learningToolRam'}
            range={range}
            handleRangeBar={handleRangeBar}
            max={maxRange.ram}
            unit={'GB'}
          />
        </div>
        <p className={cx('title')}>{t('jobToolLimit.label')}</p>
        <div className={cx('flex-row')}>
          <RangeBar
            label={'CPU Cores'}
            setting={'jobToolCpu'}
            range={range}
            handleRangeBar={handleRangeBar}
            max={maxRange.cpu}
            unit={'개'}
          />
          <RangeBar
            label={'RAM'}
            setting={'jobToolRam'}
            range={range}
            handleRangeBar={handleRangeBar}
            max={maxRange.ram}
            unit={'GB'}
          />
        </div>
      </div>
      <div className={cx('second-header-cont')}>
        {t('deploymentResourceManagement.label')}
      </div>
      <div className={cx('second-body-cont')}>
        <p className={cx('title')}>{t('workerToolLimit.label')}</p>
        <div className={cx('flex-row')}>
          <RangeBar
            label={'CPU Cores'}
            setting={'workerCpu'}
            range={range}
            handleRangeBar={handleRangeBar}
            max={maxRange.cpu}
            unit={'개'}
          />
          <RangeBar
            label={'RAM'}
            setting={'workerRam'}
            range={range}
            handleRangeBar={handleRangeBar}
            max={maxRange.ram}
            unit={'GB'}
          />
        </div>
      </div>
    </div>
  );
};

export default DefaultResource;
