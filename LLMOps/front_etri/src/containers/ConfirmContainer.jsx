import { useCallback } from 'react';
// Plugin
import { useDispatch, useSelector } from 'react-redux';

// Components
import ConfirmPopup from '@src/components/organisms/ConfirmPopup';

// Actions
import { closeConfirm } from '@src/store/modules/confirm';

function ConfirmContainer() {
  // Redux Hooks
  const dispatch = useDispatch();
  const { isOpen, confirmData } = useSelector(({ confirm }) => confirm);

  const onClose = useCallback(() => {
    dispatch(closeConfirm());
  }, [dispatch]);

  return <>{isOpen && <ConfirmPopup {...confirmData} close={onClose} />}</>;
}

export default ConfirmContainer;
