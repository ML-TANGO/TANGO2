// storybook
import { Button } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './StorageSettingModalFooter.module.scss';
const cx = classNames.bind(style);

function StorageSettingModalFooter(footerProps) {
  const { close, submit, validate, t } = footerProps;

  return (
    <div className={cx('modal-footer')}>
      <Button
        onClick={close}
        type={'none-border'}
        customStyle={{ marginRight: '12px' }}
      >
        {t('cancel.label')}
      </Button>
      <Button onClick={() => submit()} disabled={!validate}>
        {t('edit.label')}
      </Button>
    </div>
  );
}

export default StorageSettingModalFooter;
