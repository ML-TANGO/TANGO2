// CSS Module
import classNames from 'classnames/bind';
import style from './TextInput.module.scss';

const cx = classNames.bind(style);

const noop = () => {};

/**
 * 텍스트 인풋 컴포넌트
 * @param {{
 *  value: string,
 *  onChange: Function,
 *  onKeyDown: Function,
 *  placeholder: string,
 *  readOnly: boolean,
 *  disabled: boolean,
 *  leftIconPath: string,
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
 * const leftIconPath = '/images/icon/icon.svg';
 * const maxLength = 50;
 *
 * // undefined나 null면 변화 없음
 * // error면 빨간색 보더
 * const status = '';
 *
 * const onChange = () => {
 *  const { value } = e.target.value;
 *  setValue(value);
 * };
 *
 * return (
 *  <TextInput
 *    name='training-name'
 *    value={value}
 *    onChange={onChange}
 *    placeholder='placeholder text'
 *    disabled={disabled}
 *    readOnly={readOnly}
 *    testId={testId}
 *    status={status}
 *    maxLength={maxLength}
 *  />
 * )
 * -
 */
function TextInput({
  value,
  name,
  onChange = noop,
  onKeyDown = noop,
  type = 'medium',
  placeholder,
  readOnly = false,
  disabled = false,
  leftIconPath,
  testId,
  responsiveMode,
  status,
  maxLength = 50,
  autoComplete = 'on', //
  customStyle = {},
  autoFocus = false,
}) {
  return (
    <div
      className={cx(
        'fb',
        'input',
        type,
        disabled && 'disabled',
        readOnly && 'read-only',
        leftIconPath && 'left',
        leftIconPath && 'icon',
        String(value).trim() !== '' && !readOnly && !disabled && 'focus',
        responsiveMode && 'responsive',
        status,
      )}
    >
      {leftIconPath && (
        <img className={cx('left-icon')} src={leftIconPath} alt='input icon' />
      )}
      <input
        className={cx('fold')}
        name={name}
        type='text'
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        readOnly={readOnly}
        disabled={disabled}
        data-testid={testId}
        maxLength={maxLength}
        style={customStyle}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
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

export default TextInput;
