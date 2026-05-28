// Components
import { Checkbox } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './LogOptionCheckForm.module.scss';
const cx = classNames.bind(style);

function LogOptionCheckForm({ options, handleCheckbox }) {
  return (
    <div className={cx('checkbox-form')}>
      {options.map(({ label, checked }, idx) => (
        <Checkbox
          key={idx}
          label={label}
          checked={checked}
          onChange={() => handleCheckbox(idx)}
        />
      ))}
    </div>
  );
}

export default LogOptionCheckForm;
