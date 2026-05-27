// Components
import { InputNumber, StatusCard } from '@jonathan/ui-react';

import settingImage from '@images/icon/ic-lock.svg';

// Utils
import { convertBinaryByte } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
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
  t,
}) => {
  const share = true;
  const deselected = model && model.id !== id;

  const selected = prevStorageModel[0]?.id === id || (model && model.id === id);

  return (
    <li
      className={cx(
        'card',
        selected ? 'selected' : '',
        disabled && 'disabled',
        type === 'CREATE_WORKSPACE' && deselected && 'deselected',
        (type === 'EDIT_WORKSPACE' ||
          prevStorageModel.length > 0 ||
          lock === 1) &&
          (prevStorageModel[0]?.id !== id || (model && model.id !== id)) &&
          'read-only',
      )}
      onClick={() => {
        if (!disabled && !readOnly && type !== 'EDIT_WORKSPACE') {
          selectHandler({ storage: modelOptions[idx], idx, storageType });
        }
      }}
    >
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

      <div className={cx('distribution')}>
        {/* <span className={cx('type')}>
          {t('storageDistributionType.modal.label')}
        </span> */}

        {
          <StatusCard
            text={systemType === 'nfs' ? t('network.label') : t('local')}
            status={systemType === 'nfs' ? 'yellow' : 'green'}
            size='x-small'
            customStyle={{
              width: '31px',
            }}
            type='default'
          />
        }
      </div>

      <div className={cx('capacity')}>
        {/* {t('storageCapacity.label')} */}
        {/* 스토리지 용량 */}
        <span className={cx('value')}>
          {/* {convertBinaryByte(capacity === undefined ? 0 : capacity)} */}
          {totalSize ? parseInt(totalSize) : 0} GB
        </span>
      </div>

      <div className={cx('usage')}>
        {/* {t('storageRemaining.modal.label')} */}
        <span className={cx('value')}>
          {/* {type === 'EDIT_WORKSPACE'
            ? share === 1
              ? convertBinaryByte(usage === undefined ? 0 : usage)
              : convertBinaryByte(size - allocateUsed)
            : share === 1
            ? convertBinaryByte(usage === undefined ? 0 : usage)
            : convertBinaryByte(size - allocateUsed)} */}
          {freeSize ? parseInt(freeSize) : 0} GB
        </span>
      </div>
      <div className={cx('input')}>
        <InputNumber
          // placeholder={type === 'EDIT_WORKSPACE' ? 0 : 10}
          placeholder={`${freeSize ? parseInt(freeSize) : 0}`}
          name='gpuUsage'
          value={storageInputValue[idx]}
          onChange={(e) => {
            const value = e.value;

            storageInputValueHandler({ value, type: storageType, idx });
          }}
          customSize={{
            width: '110px',
            marginRight: '8px',
            textAlign: 'right',
          }}
          max={parseInt(freeSize)}
          min={0}
          // customStyle={{
          //   opacity: '0.5',
          // }}
        />
      </div>
    </li>
  );
};

export default Card;
