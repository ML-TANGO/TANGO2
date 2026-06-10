import { InputText } from '@jonathan/ui-react';

import React, { useEffect, useState } from 'react';
import { useTranslation, withTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import ModalFrame from '../ModalFrame';

import classNames from 'classnames/bind';
import style from './AddStorage.module.scss';

const cx = classNames.bind(style);

const AddStorageModal = ({ type, data }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [name, setStorageName] = useState('');
  const [ip, setIpAddress] = useState('');
  const [mountpoint, setMountPoint] = useState('');
  const [radioType, setRadioType] = useState('nfs');
  const [isValidate, setIsValiDate] = useState(false);

  const handleInput = (value, inputType) => {
    if (inputType === 'name') {
      setStorageName(value);
    }
    if (inputType === 'ip') {
      setIpAddress(value);
    }
    if (inputType === 'mount') {
      setMountPoint(value);
    }
    if (inputType === 'radio') {
      setRadioType(value);
    }
  };

  const { submit, cancel } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('ip', ip);
      formData.append('mountpoint', mountpoint);
      formData.append('type', radioType);

      const response = await callApi({
        url: 'storage',
        method: 'POST',
        body: formData,
      });

      const { status, message, error } = response;

      if (status === STATUS_SUCCESS) {
        defaultSuccessToastMessage('create');
        dispatch(closeModal(type));
        return;
      }

      errorToastMessage(error, message);
    },
  };

  useEffect(() => {
    setIsValiDate(name && ip && mountpoint);
  }, [name, ip, mountpoint]);

  return (
    <ModalFrame
      submit={newSubmit}
      cancel={cancel}
      type={type}
      title={t('addStorage.label')}
      validate={isValidate}
    >
      <h2 className={cx('title')}>{t('addStorage.label')}</h2>
      <div className={cx('form')}>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('storageName.label')}
            labelSize='large'
          >
            <InputText
              size='large'
              name='name'
              placeholder={'storage-{name}'}
              autoFocus
              value={name}
              onChange={(e) => handleInput(e.target.value, 'name')}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel labelText={t('ipAddress.label')} labelSize='large'>
            <InputText
              size='large'
              name='ip'
              placeholder={'Ex) 192.168.1.1'}
              value={ip}
              onChange={(e) => handleInput(e.target.value, 'ip')}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('mountPoint.label')}
            labelSize='large'
          >
            <InputText
              size='large'
              name='mount'
              placeholder={'Ex) /mnt'}
              value={mountpoint}
              onChange={(e) => handleInput(e.target.value, 'mount')}
            />
          </InputBoxWithLabel>
        </div>
        <div className={cx('row')}>
          <InputBoxWithLabel
            labelText={t('storageType.label')}
            labelSize='large'
            disableErrorMsg
          >
            <Radio
              name='creator'
              options={[
                { label: 'nfs', value: 'nfs' },
                { label: 'local', value: 'local' },
                { label: 'csi', value: 'csi' },
              ]}
              value={radioType}
              onChange={(e) => handleInput(e.target.value, 'radio')}
              isTranLabel={false}
            />
          </InputBoxWithLabel>
        </div>
      </div>
    </ModalFrame>
  );
};

export default withTranslation()(AddStorageModal);
