// Atom
import { Textarea } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './DeployWorkerMemoModalContent.module.scss';
const cx = classNames.bind(style);

function DeployWorkerMemoModalContent({ memo, textareaInputHandler }) {
  return (
    <div className={cx('memo-wrap')}>
      <label>
        <div>{memo ? String(memo.length) : '0'}</div>/1000
      </label>
      <Textarea
        onChange={textareaInputHandler}
        value={memo}
        customStyle={{
          height: '102px',
        }}
        maxLength={1000}
        isShowMaxLength={false}
      />
    </div>
  );
}

export default DeployWorkerMemoModalContent;
