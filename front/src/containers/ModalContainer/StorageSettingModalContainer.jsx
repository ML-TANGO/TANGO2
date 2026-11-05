import { useState, useEffect, useCallback } from 'react';
import { useDispatch } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// module
import { closeModal } from '@src/store/modules/modal';

// Components
import StorageSettingModalHeader from '@src/components/Modal/StorageSettingModal/StorageSettingModalHeader';
import StorageSettingModalContent from '@src/components/Modal/StorageSettingModal/StorageSettingModalContent';
import StorageSettingModalFooter from '@src/components/Modal/StorageSettingModal/StorageSettingModalFooter';

// Atom
import { Modal } from '@jonathan/ui-react';

function StorageSettingModalContainer({ data: modalData }) {
  const dispatch = useDispatch();

  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState(modalData.data.name);
  const [shareValue, setShareValue] = useState(modalData.data.share);
  const [createLock, setCreateLock] = useState(modalData.data.create_lock);

  const [validate, setValidate] = useState(false);
  const [nameError, setNameError] = useState(null);

  const [distributionBtn, setDistributionBtn] = useState({
    allocate: false,
    share: false,
  });

  const [newCreateBtn, setNewCreateBtn] = useState({
    allowed: false,
    limited: false,
  });

  const storageNameHandler = (value) => {
    const regType1 = /([a-z0-9-]+-?)*[a-z0-9-]$/;

    if (value === '') {
      setNameError('storageName.empty.message');
      return;
    }
    if (!value.match(regType1) || value.match(regType1)[0] !== value) {
      setNameError('storageNameRule.message');
      return;
    }
    setNameError(null);
  };

  const inputValueHandler = (value) => {
    setInputValue(value);
    storageNameHandler(value);
  };

  const validateCheck = useCallback(() => {
    let count = 0;

    if (inputValue === '') {
      count += 1;
    }
    if (!distributionBtn.allocate && !distributionBtn.share) {
      count += 1;
    }
    if (nameError) {
      count += 1;
    }

    if (count === 0) {
      setValidate(true);
    } else {
      setValidate(false);
    }
  }, [distributionBtn.allocate, distributionBtn.share, inputValue, nameError]);

  const distributionBtnHandler = (check) => {
    const newDistributionCheck = { [check]: true };

    if (check === 'allocate') {
      setShareValue(0);
      newDistributionCheck.share = false;
    } else {
      setShareValue(1);
      newDistributionCheck.allocate = false;
    }

    setDistributionBtn(newDistributionCheck);
  };

  const onsubmit = () => {
    modalData.submit.func({
      id: modalData.data.id,
      name: inputValue,
      share: shareValue,
      lock: createLock,
    });
  };

  const newCreateHandler = (check) => {
    const newCheck = { [check]: true };

    if (check === 'allowed') {
      setCreateLock(0);
      newCheck.limited = false;
    } else {
      setCreateLock(1);
      newCheck.allowed = false;
    }

    setNewCreateBtn(newCheck);
  };

  const headerProps = {
    t,
  };

  const footerProps = {
    close: () => {
      dispatch(closeModal('SETTING_STORAGE'));
    },
    cancel: modalData.cancel.text,
    submit: onsubmit, // text and func
    validate,
    storageName: modalData.data.name,
    t,
  };

  const contentProps = {
    data: {
      newCreateHandler,
      distributionBtnHandler,
      validateCheck,
      distributionBtn,
      inputValue,
      inputValueHandler,
      newCreateBtn,
      nameError,
      shareValue,
      createLock,
      workspaces: modalData.data.workspaces,
      storageName: modalData.data.name,
    },
  };

  useEffect(() => {
    validateCheck();
  }, [
    inputValue,
    newCreateBtn,
    distributionBtn,
    modalData.data.nameError,
    validateCheck,
  ]);

  useEffect(() => {
    const distributionInitial = { allocate: false, share: false };
    const createInitial = { allowed: false, limited: false };
    if (modalData.data.share === 0) {
      distributionInitial.allocate = true;
      distributionInitial.share = false;
    } else if (modalData.data.share === 1) {
      distributionInitial.allocate = false;
      distributionInitial.share = true;
    }

    if (modalData.data.create_lock === 0) {
      createInitial.allowed = true;
      createInitial.limited = false;
    } else if (modalData.data.create_lock === 1) {
      createInitial.allowed = false;
      createInitial.limited = true;
    }
    setNewCreateBtn(createInitial);
    setDistributionBtn(distributionInitial);
  }, [modalData.data.share, modalData.data.create_lock]);

  return (
    <>
      <Modal
        HeaderRender={StorageSettingModalHeader}
        ContentRender={StorageSettingModalContent}
        FooterRender={StorageSettingModalFooter}
        headerProps={headerProps}
        contentProps={contentProps}
        footerProps={footerProps}
        topAnimation='calc(50% - 356px)'
      />
    </>
  );
}
export default StorageSettingModalContainer;
