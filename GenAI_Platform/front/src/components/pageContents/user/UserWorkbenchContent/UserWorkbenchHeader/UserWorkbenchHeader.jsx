import React, { useCallback } from 'react';
import { useDispatch } from 'react-redux';

import PageTitle from '@src/components/atoms/PageTitle';

import { closeModal, openModal } from '@src/store/modules/modal';

import classNames from 'classnames/bind';
import style from './UserWorkbenchHeader.module.scss';

const cx = classNames.bind(style);

const UserWorkbenchHeader = React.memo(({ trainingName, t }) => {
  const dispatch = useDispatch();

  const handleGuideModal = useCallback((dispatch, openModal, closeModal) => {
    dispatch(
      openModal({
        modalType: 'VISUALIZATION_GUIDE',
        modalData: {
          submit: {
            text: 'confirm.label',
            func: () => {
              dispatch(closeModal('VISUALIZATION_GUIDE'));
            },
          },
        },
      }),
    );
  }, []);

  return (
    <div className={cx('title-box')}>
      <PageTitle>{trainingName}</PageTitle>
      <button
        className={cx('visual-guide-btn')}
        onClick={() => handleGuideModal(dispatch, openModal, closeModal)}
      >
        {t('visualizationGuide.label')}
      </button>
    </div>
  );
});

export default UserWorkbenchHeader;
