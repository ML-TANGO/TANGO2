// CSS Module
import classNames from 'classnames/bind';
import style from './InputLabel.module.scss';

const cx = classNames.bind(style);

/**
 * 인풋 라벨 컴포넌트 (Atom)
 * @param {{
 *  labelText: string,
 *  optionalText: string | undefined,
 *  labelRight: string | JSX.Element | undefined
 *  labelSize: string | undefined,
 *  optionalSize: string | undefined,
 * }} param
 * @component
 * @example
 *
 * return (
 *  <InputLabel
 *    labelText='Training Name'
 *    optionalText='Optional'
 *    labelRight={}
 *    labelSize='medium'
 *    optionalSize='medium'
 *  />
 * );
 */
function InputLabel({
  labelText,
  optionalText,
  labelRight,
  labelSize,
  optionalSize,
  labelStyle,
  labelDescText,
  labelDescStyle,
}) {
  return (
    <label className={cx('label-wrap')} style={labelStyle}>
      <span className={cx('label', labelSize)}>{labelText}</span>
      <span style={labelDescStyle}>{labelDescText}</span>
      {optionalText && (
        <span className={cx('optional', optionalSize)}>{optionalText}</span>
      )}
      {labelRight && <div className={cx('label-right-item')}>{labelRight}</div>}
    </label>
  );
}

export default InputLabel;
