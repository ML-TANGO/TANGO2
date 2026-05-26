// storybook
import { ButtonV2 } from '@jonathan/ui-react';

import style from '@src/components/Modal/DockerImageDeleteModal/DockerImageDeleteModal.module.scss';

// CSS module
import classNames from 'classnames/bind';

const cx = classNames.bind(style);

function DockerImageDeleteModalFooter(footerProps) {
  const { close, cancel, submit, t, deleteList } = footerProps;
  return (
    <div className={cx('modal-footer')} style={{ paddingTop: 0 }}>
      <div className={cx('right')}>
        <ButtonV2
          label={t(cancel)}
          onClick={close}
          type='clear'
          size='l'
          colorType='gray'
        />
        <ButtonV2
          label={t(submit.text)}
          onClick={() => submit.func(deleteList)}
          colorType='red'
          size='l'
        />
      </div>
    </div>
  );
}

export default DockerImageDeleteModalFooter;
