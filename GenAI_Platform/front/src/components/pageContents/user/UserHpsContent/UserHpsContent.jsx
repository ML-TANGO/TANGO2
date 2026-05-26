// i18n
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { closeModal, openModal } from '@src/store/modules/modal';

import HpsDetail from './HpsDetail';

import classNames from 'classnames/bind';
// CSS module
import style from './UserHpsContent.module.scss';

const cx = classNames.bind(style);

const HpsContent = ({ wid, tid }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const [trainName, setTrainName] = useState('');

  const openGuideModal = () => {
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
  };

  return (
    <div className={cx('container')}>
      <div className={cx('process-name')}>
        <span>{trainName}</span>
        <button className={cx('visual-guide-btn')} onClick={openGuideModal}>
          {t('visualizationGuide.label')}
        </button>
      </div>
      <HpsDetail wid={wid} tid={tid} setTrainName={setTrainName} />
    </div>
  );
};

export default HpsContent;
