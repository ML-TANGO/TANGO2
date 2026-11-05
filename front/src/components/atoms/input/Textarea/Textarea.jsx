// CSS Module
import classNames from 'classnames/bind';
import style from './Textarea.module.scss';

const cx = classNames.bind(style);

const noop = () => {};

/**
 * Textarea 컴포넌트
 * @param {{
 *  value: string,
 *  onChange: Function,
 *  onKeyDown: Function,
 *  placeholder: string,
 *  readOnly: boolean,
 *  disabled: boolean,
 *  testId: string,
 *  responsiveMode: boolean,
 *  status: undefined | null | 'success' | 'error',
 *  maxLength: number,
 * }}
 * @component
 * @example
 *
 * const [value, setValue] = useState('');
 * const disabled = false;
 * const readOnly = false;
 * const testId = 'text-input-id';
 * const maxLength = 1000;
 *
 * // undefined나 null이면 변화 없음
 * // error면 빨간색 보더
 * const status = '';
 *
 * const onChange = () => {
 *  const { value } = e.target.value;
 *  setValue(value);
 * };
 *
 * return (
 *  <Textarea
 *    name='training-name'
 *    value={value}
 *    onChange={onChange}
 *    placeholder='placeholder text'
 *    disabled={disabled}
 *    readOnly={readOnly}
 *    testId={testId}
 *    status={status}
 *    rows = {row}
 *    maxLength={maxLength}
 *  />
 * )
 * -
 */
function Textarea({
  value,
  name,
  onChange = noop,
  onKeyDown = noop,
  type = 'medium',
  placeholder,
  disabled = false,
  readOnly = false,
  testId,
  responsiveMode,
  status,
  rows = 3,
  maxLength = 1000,
  optionObj,
}) {
  return (
    <div
      className={cx(
        'fb',
        'input',
        type,
        disabled && 'disabled',
        readOnly && 'read-only',
        String(value).trim() !== '' && !readOnly && !disabled && 'focus',
        responsiveMode && 'responsive',
        status,
      )}
    >
      <span className={cx('text-length-box')}>
        <span className={cx('text-length')}>{value.length}</span>/{maxLength}
      </span>
      <textarea
        value={value}
        onKeyDown={onKeyDown}
        onChange={(e) => {
          if (e.target.value.length > maxLength) {
            e.target.value = e.target.value.slice(0, maxLength);
          }
          onChange(e);
        }}
        name={name}
        placeholder={placeholder}
        rows={rows}
        maxLength={maxLength}
        readOnly={readOnly}
        disabled={disabled}
        data-testid={testId}
        {...optionObj}
      />
      <button
        className={cx('close-btn')}
        value=''
        onClick={() => {
          onChange({ target: { value: '', name } });
        }}
      >
        <img src='/images/icon/close-c.svg' alt='close button' />
      </button>
    </div>
  );
}

export default Textarea;
