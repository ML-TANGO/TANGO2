import { useDispatch } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Actions
import { openModal } from '@src/store/modules/modal';

// Atoms
import Button from '@src/components/atoms/button/Button';

// CSS Module
import classNames from 'classnames/bind';
import style from './DroneChallengeBtnBox.module.scss';
const cx = classNames.bind(style);

const SERVICE_LOGO_IMG = import.meta.env.VITE_REACT_APP_SERVICE_LOGO_IMG;

function DroneChallengeBtnBox({ trainingId, refreshInfo }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const openDroneChallengeModal = () => {
    dispatch(
      openModal({
        modalType: 'DRONE_CHALLENGE',
        modalData: {
          submit: {
            func: () => {
              refreshInfo();
            },
          },
          cancel: {
            text: t('close.label'),
          },
          trainingId,
        },
      }),
    );
  };

  return (
    <div className={cx('challenge-container')}>
      <div className={cx('logo-box')}>
        <img src={SERVICE_LOGO_IMG} alt='DNA+DRONE' className={cx('logo')} />
      </div>
      <div className={cx('btn-box')}>
        <div className={cx('challenge-name')}>
          <span className={cx('dark')}>DNA+DRONE</span> CHALLENGE
        </div>
        <Button size='x-large' type='primary' onClick={openDroneChallengeModal}>
          답안지 테스트 &amp; 제출
        </Button>
      </div>
    </div>
  );
}

export default DroneChallengeBtnBox;
