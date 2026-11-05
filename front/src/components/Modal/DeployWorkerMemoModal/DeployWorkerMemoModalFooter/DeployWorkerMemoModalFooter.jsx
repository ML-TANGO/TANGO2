import { useDispatch } from 'react-redux';

// Atom
import { Button } from '@jonathan/ui-react';

// module
import { closeModal } from '@src/store/modules/modal';

// style
import classNames from 'classnames/bind';
import style from './DeployWorkerMemoModalFooter.module.scss';
const cx = classNames.bind(style);

function DeployWorkerMemoModalFooter({ submit, type, t }) {
  const dispatch = useDispatch();
  return (
    <div className={cx('btn-wrap')}>
      <Button
        type='primary-reverse'
        onClick={() => {
          dispatch(closeModal(type));
        }}
      >
        {t('cancel.label')}
      </Button>
      <Button onClick={submit} customStyle={{ marginLeft: '12px' }}>
        {t('confirm.label')}
      </Button>
    </div>
  );
}

export default DeployWorkerMemoModalFooter;
