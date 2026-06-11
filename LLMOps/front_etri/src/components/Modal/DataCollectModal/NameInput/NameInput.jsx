import { InputText } from '@tango/ui-react';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

export default function NameInput({
  value,
  labelText,
  placeholder,
  isError,
  handleName,
  isReadOnly = false,
}) {
  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={labelText}
        labelSize='large'
        disableErrorMsg
      >
        <InputText
          placeholder={placeholder}
          value={value}
          onChange={(e) => handleName(e.target.value)}
          status={isError ? 'error' : 'default'}
          options={{ maxLength: 50 }}
          autoFocus={true}
          customStyle={{ fontSize: '14px' }}
          disableLeftIcon
          disableClearBtn
          isReadOnly={isReadOnly}
        />
      </InputBoxWithLabel>
    </div>
  );
}
