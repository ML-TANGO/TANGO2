// i18n
import { withTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './CheckboxList.module.scss';
const cx = classNames.bind(style);

const noop = () => {};

const CheckboxList = ({
  label,
  options,
  error,
  onChange = noop,
  horizontal,
  optional,
  disableErrorText,
  customStyle,
  labelRight,
  t,
}) => {
  return (
    <div className={cx('fb', 'input', 'input-wrap')}>
      {(label || labelRight) && (
        <div className={cx('label-wrap')}>
          <label className={cx('fb', 'label')}>
            {t(label)}{' '}
            {optional && (
              <span className={cx('optional')}>- {t('optional.label')}</span>
            )}
          </label>
          {labelRight && (
            <div className={cx('label-right-item')}>{labelRight}</div>
          )}
        </div>
      )}
      <div
        className={cx('checkboxes-container', horizontal && 'horizontal')}
        style={customStyle}
      >
        {options.map(
          (
            {
              label: labelItem,
              value,
              name,
              subtext,
              checked,
              disabled,
              readOnly,
            },
            idx,
          ) => (
            <label
              key={idx}
              className={cx(
                'check-container',
                disabled && 'disabled',
                readOnly && 'readOnly',
              )}
            >
              <input
                type='checkbox'
                className={cx('checkmark')}
                name={name}
                value={value}
                checked={checked}
                onChange={(e) => !readOnly && onChange(e, idx)}
                disabled={disabled}
                readOnly
              />
              <span className={cx('checkmark')}></span>
              <span className={cx('labeltext', readOnly && 'readOnly')}>
                {t(labelItem)}
              </span>
              {subtext && (
                <span className={cx('subtext', readOnly && 'readOnly')}>
                  {!horizontal &&
                    subtext &&
                    subtext.map((text, sidx) => (
                      <span key={sidx}>{t(text)}</span>
                    ))}
                </span>
              )}
            </label>
          ),
        )}
      </div>
      {!disableErrorText && (
        <span className={cx('error')}>{error && error}</span>
      )}
    </div>
  );
};

export default withTranslation()(CheckboxList);
