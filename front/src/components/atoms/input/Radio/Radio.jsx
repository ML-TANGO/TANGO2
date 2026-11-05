import { useTranslation } from 'react-i18next';

// CSS module
import classNames from 'classnames/bind';
import style from './Radio.module.scss';

const cx = classNames.bind(style);

const noop = () => {};

/**
 *
 * @param {{
 *  options: Array,
 *  value: string,
 *  name: string,
 *  onChange: Function,
 *  readOnly: boolean,
 *  customStyle: object,
 *  testId: string,
 * }}
 */
function Radio({
  options,
  value,
  name,
  onChange = noop,
  readOnly,
  customStyle = {},
  testId,
  isTranLabel = true,
  labelCustomStyle,
  isShowAllDesc = true,
  isLabelColor = false,
}) {
  const { t } = useTranslation();

  return (
    <div className={cx('radio-box')} style={customStyle} data-testid={testId}>
      {options.map(
        (
          { label, value: val, disabled, icon, labelStyle, desc, descStatus },
          idx,
        ) => (
          <label
            key={idx}
            className={cx('radio-btn', disabled && 'disabled')}
            style={labelStyle}
          >
            <input
              type='radio'
              name={name}
              value={val}
              checked={val === value}
              onChange={onChange}
              disabled={readOnly ? value !== val : disabled}
            />

            {icon && (
              <img className={cx('label-icon')} src={icon} alt={label} />
            )}
            {isTranLabel ? (
              <span
                className={cx(
                  `${
                    isLabelColor && val === value
                      ? 'selected-label'
                      : 'not-selected-label'
                  }`,
                  readOnly && val !== value && 'readonly-selected-label',
                )}
                style={labelCustomStyle}
              >
                {t(label)}
              </span>
            ) : (
              <span
                className={cx(
                  `${
                    isLabelColor && val === value
                      ? 'selected-label'
                      : 'not-selected-label'
                  }`,
                  readOnly && val !== value && 'readonly-selected-label',
                )}
                style={labelCustomStyle}
              >
                {label}
              </span>
            )}
            {isShowAllDesc
              ? desc &&
                descStatus !== null && (
                  <span
                    className={cx(
                      'desc',
                      `${descStatus ? 'recommand' : 'warning'}`,
                    )}
                  >
                    {desc}
                  </span>
                )
              : desc &&
                descStatus !== null &&
                val === value && (
                  <span
                    className={cx(
                      'desc',
                      `${descStatus ? 'recommand' : 'warning'}`,
                    )}
                  >
                    {desc}
                  </span>
                )}
          </label>
        ),
      )}
    </div>
  );
}

export default Radio;
