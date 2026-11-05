// i18n
import { withTranslation } from 'react-i18next';

// Components
import ModalFrame from '../ModalFrame';

// CSS module
import classNames from 'classnames/bind';
import style from './CheckpointModal.module.scss';
const cx = classNames.bind(style);

const CheckpointModal = ({ type, data, t }) => {
  const { submit, groupId } = data;
  return (
    <ModalFrame submit={submit} type={type} validate>
      <h2 className={cx('title')}>{t('checkpoint.label')}</h2>
      <div className={cx('form')}>
        <p>그룹아이디: {groupId}</p>
        <p>체크포인트 다운로드/삭제 기능 개발 예정</p>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(CheckpointModal);
