import { Popup } from '@tango/ui-react';

import { useCallback, useEffect, useState } from 'react';
// Plugin
import { useDispatch, useSelector } from 'react-redux';

import { handleClosePopup } from '@src/store/modules/popupState';

import classNames from 'classnames/bind';
import style from './PopupContainer.module.scss';

const cx = classNames.bind(style);

function PopupContainer() {
  const dispatch = useDispatch();
  const {
    isOpen,
    type,
    icon,
    isAnimation,
    frontTitle,
    popupTitle,
    popupContents,
    cancelBtnLabel,
    submitBtnLabel,
    handleCancel,
    handleSubmit,
    style,
  } = useSelector(({ popupState }) => popupState);

  const [isLoading, setIsLoading] = useState(false);

  const handleSubmitBtn = async () => {
    setIsLoading(true);
    await handleSubmit();
    setIsLoading(false);
    dispatch(handleClosePopup());
  };

  const handleLastCancel = () => {
    if (handleCancel) {
      handleCancel();
    }
    dispatch(handleClosePopup(type));
  };

  return (
    <>
      {isOpen && (
        <div className={cx('shadow')}>
          <div className={cx('popup')}>
            <Popup
              type={type}
              icon={icon}
              isAnimation={isAnimation}
              isLoading={isLoading}
              frontTitle={frontTitle}
              popupTitle={popupTitle}
              popupContents={popupContents}
              cancelBtnLabel={cancelBtnLabel}
              submitBtnLabel={submitBtnLabel}
              handleCancel={handleLastCancel}
              handleSubmit={handleSubmitBtn}
              style={style}
            />
          </div>
        </div>
      )}
    </>
  );
}

export default PopupContainer;
