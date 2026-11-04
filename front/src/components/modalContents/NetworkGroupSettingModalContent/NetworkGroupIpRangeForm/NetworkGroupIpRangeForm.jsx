// i18n
import { useTranslation } from 'react-i18next';

// Components
import InputLabel from '@src/components/atoms/input/InputLabel';
import { InputNumber, Selectbox, Button } from '@jonathan/ui-react';

// Icons
import ErrorIcon from '@src/static/images/icon/icon-error-c-red.svg';

// CSS module
import classNames from 'classnames/bind';
import style from './NetworkGroupIpRangeForm.module.scss';
const cx = classNames.bind(style);

function NetworkGroupIpRangeForm({
  ip,
  ipRangeStart,
  ipRangeEnd,
  subnetMaskOption,
  subnetMask,
  getIpRange,
  error,
  validate,
  inputHandler,
  selectHandler,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('form')}>
      <div className={cx('ip')}>
        <label>{t('ipAddress.label')}</label>
        <InputNumber
          size='medium'
          status={error ? 'error' : 'default'}
          value={ip[0]}
          min={0}
          max={255}
          name='ip1'
          onChange={inputHandler}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          status={error ? 'error' : 'default'}
          value={ip[1]}
          min={0}
          max={255}
          name='ip2'
          onChange={inputHandler}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          status={error ? 'error' : 'default'}
          value={ip[2]}
          min={0}
          max={255}
          name='ip3'
          onChange={inputHandler}
          isReadOnly={subnetMask.value === 16}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          status={error ? 'error' : 'default'}
          value={ip[3]}
          min={0}
          max={255}
          name='ip4'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('slash')}>/</span>
        <Selectbox
          type='group'
          size='medium'
          status={error ? 'error' : 'default'}
          list={subnetMaskOption}
          selectedItem={subnetMask}
          customStyle={{
            globalForm: { width: '110px', marginRight: '8px' },
            selectboxForm: { width: '110px' },
          }}
          onChange={(value) => {
            selectHandler(value);
          }}
        />
        <Button
          type='primary-light'
          size='medium'
          disabled={!validate}
          onClick={getIpRange}
        >
          {t('network.ipRange.check.label')}
        </Button>
      </div>
      <div className={cx('error-message')}>
        {error && (
          <>
            <img className={cx('icon')} src={ErrorIcon} alt='error' />
            <span> {t('network.ipRange.error.message')}</span>
          </>
        )}
      </div>
      <InputLabel
        labelText={t('network.ipRange.available.label')}
        labelSize='large'
      />
      <div className={cx('ip-range')}>
        <label>From</label>
        <InputNumber
          size='medium'
          value={ipRangeStart[0]}
          min={0}
          max={255}
          name='from1'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          value={ipRangeStart[1]}
          min={0}
          max={255}
          name='from2'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          value={ipRangeStart[2]}
          min={0}
          max={255}
          name='from3'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          value={ipRangeStart[3]}
          min={0}
          max={255}
          name='from4'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
      </div>
      <div className={cx('ip-range')}>
        <label>To</label>
        <InputNumber
          size='medium'
          value={ipRangeEnd[0]}
          min={0}
          max={255}
          name='to1'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          value={ipRangeEnd[1]}
          min={0}
          max={255}
          name='to2'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          value={ipRangeEnd[2]}
          min={0}
          max={255}
          name='to3'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
        <span className={cx('dot')}>.</span>
        <InputNumber
          size='medium'
          value={ipRangeEnd[3]}
          min={0}
          max={255}
          name='to4'
          isReadOnly={true}
          disableIcon={true}
          customSize={{ width: '80px', textAlign: 'center' }}
        />
      </div>
    </div>
  );
}

export default NetworkGroupIpRangeForm;
