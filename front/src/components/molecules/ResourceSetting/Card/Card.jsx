// Components
import { Badge, InputNumber } from '@jonathan/ui-react';

import settingImage from '@images/icon/ic-lock.svg';

import classNames from 'classnames/bind';
import style from './Card.module.scss';

const cx = classNames.bind(style);

const Card = ({
  id,
  name,
  type,
  disabled,
  prevStorageModel,
  model,
  totalSize,
  modelOptions,
  selectHandler,
  storageType,
  storageInputValueHandler,
  storageInputValue,
  readOnly,
  idx,
  freeSize,
  systemType,
  lock,
  prevStorageSize,
  t,
  customStyle,
  inputMaxValue,
}) => {
  const deselected = model && model.id !== id;

  const selected = prevStorageModel[0]?.id === id || (model && model.id === id);

  const storageFreeSize = freeSize ? `${parseInt(freeSize)} GB` : '0 GB';

  return (
    <li
      className={cx(
        'card',
        selected ? 'selected' : '',
        disabled && 'disabled',
        type === 'CREATE_WORKSPACE' && deselected && 'deselected',
        /*type === 'EDIT_WORKSPACE' ||*/
        (prevStorageModel.length > 0 || lock === 1) &&
          (prevStorageModel[0]?.id !== id || (model && model.id !== id)) &&
          'read-only',
      )}
      onClick={() => {
        if (!disabled && !readOnly /*&& type !== 'EDIT_WORKSPACE'*/) {
          selectHandler({ storage: modelOptions[idx], idx, storageType });
        }
      }}
      style={customStyle}
    >
      <div className={cx('distribution')}>
        <Badge
          label={systemType === 'nfs' ? t('network.label') : t('local')}
          type={systemType === 'nfs' ? 'primary-2' : 'red'}
          size='xl'
        />
      </div>
      <div className={cx('name-box', lock === 1 && 'lock')}>
        <div className={cx('storage-name')} title={name}>
          {name}
        </div>
        <div className={cx('icon')}>
          {lock === 1 && (
            <img
              src={settingImage}
              alt='lock'
              style={{
                width: '24px',
                height: '24px',
              }}
            />
          )}
        </div>
      </div>
      <div className={cx('capacity')}>
        {/* 스토리지 용량 */}
        <span className={cx('value')}>
          {totalSize ? parseInt(totalSize) : 0} GB
        </span>
      </div>

      <div className={cx('usage')}>
        <span className={cx('value')}>{storageFreeSize}</span>
      </div>
      <div className={cx('input')}>
        <InputNumber
          placeholder={storageFreeSize}
          name='gpuUsage'
          value={storageInputValue}
          onChange={(e) => {
            const value = e.value;
            if (parseInt(inputMaxValue) < value) return;
            storageInputValueHandler({ value, type: storageType, id });
          }}
          min={0}
          max={parseInt(inputMaxValue)}
          customSize={{
            width: '100%',
          }}
          isReadOnly={disabled}
        />
        <span className={cx('gb' /*type === 'EDIT_WORKSPACE' && 'opacity'*/)}>
          GB
        </span>
      </div>
    </li>
  );
};

export default Card;
