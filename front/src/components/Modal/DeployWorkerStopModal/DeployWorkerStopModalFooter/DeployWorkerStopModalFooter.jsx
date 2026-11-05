import { useDispatch } from 'react-redux';

// Atom
import { Button } from '@jonathan/ui-react';

// module
import { closeModal } from '@src/store/modules/modal';

// style
import classNames from 'classnames/bind';
import style from './DeployWorkerStopModalFooter.module.scss';
const cx = classNames.bind(style);

function DeployWorkerStopModalFooter({ submit, type, t }) {
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
      <Button onClick={submit.func} customStyle={{ marginLeft: '12px' }}>
        {t('stopWorker.label')}
      </Button>
    </div>
  );
}

export default DeployWorkerStopModalFooter;
