// i18n
import { useTranslation } from 'react-i18next';

// Icons
import upIcon from './imgs/up.png';
import downIcon from './imgs/down.png';

// CSS module
import classNames from 'classnames/bind';
import style from './Number.module.scss';
const cx = classNames.bind(style);

function Number ({
  label,
  miniLabel,
  value,
  status = '',
  onChange,
  name,
  placeholder = '',
  error,
  info,
  min = 'number',
  max = 'number',
  disabled,
  size,
  readOnly,
  customStyle,
  disabledErrorText,
  step = 'any',
  testId,
}) {
  const { t } = useTranslation();
  // 키보드 입력시 최소/최대 값에 맞춰 입력 제한
  function enforceMinMax(e) {
    const el = e.target;
    if (el.value !== '') {
      if (parseInt(el.value) < parseInt(el.min)) {
        el.value = el.min;
      }
      if (parseInt(el.value) > parseInt(el.max)) {
        el.value = el.max;
      }
    }
  }

  return (
    <div className={cx('input-wrap')} style={customStyle}>
      {label && <label className={cx('label')}>{t(label)}</label>}
      {miniLabel && <div className={cx('mini-label')}>{t(miniLabel)}</div>}
      <div
        className={cx(
          'fb',
          'input',
          disabled && 'disabled',
          size,
          status,
          !readOnly && !disabled && 'focus',
        )}
      >
        {/* input 박스 */}
        <input
          type='number'
          step={step}
          pattern='[0-9]*'
          placeholder={t(placeholder)}
          onChange={onChange}
          onKeyUp={(e) => enforceMinMax(e)}
          name={name}
          value={value}
          min={min}
          max={max}
          readOnly={readOnly}
          disabled={disabled}
          data-testid={testId}
          onWheel={(e) => e.currentTarget.blur()}
        />
        {/* 화살표 버튼 */}
        <div className={cx('btn-box')}>
          <button
            className={cx('up-btn')}
            onClick={() => {
              if (readOnly || disabled) {
                return;
              }
              const currentVal = parseInt(value, 10);
              if (value === '') {
                onChange({ target: { value: min || 0, name } });
              } else if (currentVal < max || max === 'number') {
                onChange({ target: { value: `${currentVal + 1}`, name } });
              }
            }}
          >
            <img src={upIcon} alt='아이콘' />
          </button>
          <button
            className={cx('down-btn')}
            onClick={() => {
              if (readOnly || disabled) {
                return;
              }
              const currentVal = parseInt(value, 10);
              if (value === '') {
                onChange({ target: { value: min || 0, name } });
              } else if (currentVal > min || min === 'number') {
                onChange({ target: { value: `${currentVal - 1}`, name } });
              }
            }}
          >
            <img src={downIcon} alt='아이콘' />
          </button>
        </div>
      </div>
      {!disabledErrorText && (
        <span className={cx('error-info')}>
          {/* 우선순위 error > info */}
          {error && <span className={cx('error')}>{t(error)}</span>}
          {!error && info && <span className={cx('info')}>{t(info)}</span>}
        </span>
      )}
    </div>
  );
}

export default Number;
