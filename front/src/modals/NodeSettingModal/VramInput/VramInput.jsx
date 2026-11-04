import { InputNumber } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from '../VcpuInput/VInput.module.scss';

const cx = classNames.bind(style);
const VramInput = ({ t, value, onChange, max, min }) => {
  return (
    <div className={cx('column-cont')}>
      <div className={cx('row-cont')}>
        <span className={cx('bold-txt')}>RAM {t('allocateGpu.label')}</span>
        <div className={cx('inner-row-cont')}>
          <span>{t('storageAvailable.label')}</span>
          <span>{max - value}</span>
        </div>
      </div>
      <InputNumber
        placeholder={`사용가능: ${max - value}`}
        onChange={({ value }) => onChange(value)}
        value={value}
        max={max}
        min={min}
        customSize={{ width: '268px' }}
      />
    </div>
  );
};

export default VramInput;
