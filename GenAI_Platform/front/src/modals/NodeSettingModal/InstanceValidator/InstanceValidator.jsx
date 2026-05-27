import { ButtonV2 } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './InstanceValidator.module.scss';

const cx = classNames.bind(style);

const InstanceValidator = ({
  t,
  isValidate,
  isLastInstanceList,
  errorMsg,
  instanceName,
  instanceCount,
  isAddBtnDisabled,
  handleDelete,
  handleAdd,
  handleAllClear,
}) => {
  return (
    <div className={cx('validation-cont')}>
      <div className={cx('validation-check-cont')}>
        <p className={cx('name-paragraph')}>
          <span>
            {t('createable.label')} {instanceName}
          </span>
          <span>
            {t('instanceCount.label')} : {instanceCount}
            {t('eaOnly.label')}
          </span>
        </p>
      </div>
      <div className={cx('footer-cont')}>
        <div className={cx('isValidate-cont')}>
          <p className={cx(isValidate ? 'success' : 'warn')}>
            {isValidate ? t('node.instance.success.message') : errorMsg}
          </p>
        </div>
        <div className={cx('btn-cont')}>
          <ButtonV2 colorType='red' size='l' onClick={() => handleDelete()}>
            {t('remove.label')}
          </ButtonV2>
        </div>
      </div>
      <div className={cx('line')} />
      {isLastInstanceList && (
        <div className={cx('last-index-btn-cont')}>
          <ButtonV2
            size='l'
            colorType='lightRed'
            label={t('Instance.reset.btn.label')}
            onClick={handleAllClear}
          />
          <ButtonV2
            size='l'
            type='clear'
            label={t('Instance.add.btn.label')}
            onClick={() => handleAdd()}
            disabled={isAddBtnDisabled}
          />
        </div>
      )}
    </div>
  );
};

export default InstanceValidator;
