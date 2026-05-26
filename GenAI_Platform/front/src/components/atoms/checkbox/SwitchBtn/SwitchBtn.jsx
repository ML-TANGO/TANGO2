// CSS Module
import classNames from 'classnames/bind';
import style from './SwitchBtn.module.scss';

const cx = classNames.bind(style);

/**
 * 스위치 버튼 컴포넌트
 * @component
 * @example
 *
 * const [checked, setChecked] = useState(false);
 *
 * return (
 *  <SwitchBtn
 *    onChange={() => {
 *      setChecked(!checked);
 *    }}
 *    checked={checked}
 *  />
 * );
 *
 *
 * -
 */
function SwitchBtn({ onChange, checked, disabled }) {
  return (
    <label className={cx('switch')}>
      <input
        type='checkbox'
        onChange={onChange}
        checked={checked}
        disabled={disabled}
      />
      <span></span>
    </label>
  );
}

export default SwitchBtn;
