// CSS module
import CloseIcon from '@src/static/images/icon/00-ic-popup-close.svg';

import style from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModal.module.scss';

import classNames from 'classnames/bind';

const cx = classNames.bind(style);

function DockerImageDeleteModalHeader(headerPorps) {
  const { t, handleClose } = headerPorps;
  return (
    <>
      <h2 className={cx('title')}>{t('deleteDockerImagePopup.title.label')}</h2>
      <img
        className={cx('close-btn')}
        onClick={handleClose}
        src={CloseIcon}
        alt='close-btn'
      />
    </>
  );
}

export default DockerImageDeleteModalHeader;
