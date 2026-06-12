// Components
import { InputText } from '@tango/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './DeleteConfirmMessage.module.scss';

const cx = classNames.bind(style);

function DeleteConfirmMessage({
  notice,
  confirmMessage,
  inputMessage,
  textInputHandler,
}) {
  return (
    <div className={cx('input-box')}>
      {notice && (
        <ul className={cx('notice')}>
          {notice.split('\n').map((text, i) => (
            <li key={i}>
              {text} <br />
            </li>
          ))}
        </ul>
      )}
      <InputText
        placeholder={confirmMessage}
        value={inputMessage}
        onChange={textInputHandler}
        disableLeftIcon
        disableClearBtn
        customStyle={{ height: '44px' }}
      />
    </div>
  );
}

export default DeleteConfirmMessage;
