// i18n

// Components
import { withTranslation } from 'react-i18next';

import { Button, Tooltip } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './ParameterInput.module.scss';

const cx = classNames.bind(style);

const ParameterInput = ({
  label,
  status = '',
  onChange,
  onAdd,
  name,
  onRemove,
  error,
  readOnly,
  isLowercase,
  multiValues,
  t,
}) => {
  console.log('multiValues : ', multiValues);
  const objKeys = multiValues.length > 0 ? Object.keys(multiValues[0]) : [];

  const batchSizeValid = objKeys.length === 0;
  if (batchSizeValid) {
    multiValues = [[]];
  }

  return (
    <div className={cx('fb', 'input', status, 'input-wrap')}>
      {label && <label className={cx('fb', 'label')}>{t(label)}</label>}
      {multiValues && (
        <div className={cx('item-list')}>
          {multiValues.map((param, idx) => (
            <div key={idx} className={cx('fb', 'input', 'item')}>
              <div className={cx('input-wrap')}>
                <div className={cx('title-box')}>
                  {!batchSizeValid ? (
                    <>
                      <label className={cx('param-key')}>
                        {t('name.label')}
                      </label>
                      <label className={cx('param-value')}>
                        {t('value.label')}
                      </label>
                      <button
                        className={cx(
                          'remove-btn',
                          multiValues.length === 1 && 'disabled',
                        )}
                        onClick={() => {
                          if (multiValues.length !== 1) {
                            onRemove(idx);
                          }
                        }}
                      ></button>
                    </>
                  ) : (
                    <span className={cx('param-key')}>
                      {t('noData.message')}
                    </span>
                  )}
                </div>
                {!batchSizeValid ? (
                  <>
                    {objKeys.map((key) => (
                      <div className={cx('input-box-item')} key={key}>
                        <div className={cx('param-key')}>
                          <label>{key}</label>
                          {param[key]?.description && (
                            <Tooltip contents={param[key].description} />
                          )}
                        </div>
                        <input
                          className={cx(
                            'param-value',
                            isLowercase && 'lowercase',
                          )}
                          type='text'
                          placeholder={t('enterValue.placeholder')}
                          onChange={(e) => {
                            onChange(e, idx, key);
                          }}
                          name={name}
                          value={param[key]?.default_value}
                          idx={idx}
                          readOnly={readOnly}
                        />
                      </div>
                    ))}
                  </>
                ) : (
                  ''
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {multiValues.length < 10 && (
        <Button type='secondary' size='medium' onClick={onAdd}>
          {t('add.label')}
        </Button>
      )}
      <span className={cx('error')}>{error && error}</span>
    </div>
  );
};

export default withTranslation()(ParameterInput);
