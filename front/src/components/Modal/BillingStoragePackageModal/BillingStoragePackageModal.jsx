import { InputText } from '@jonathan/ui-react';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { callApi, STATUS_SUCCESS } from '@src/network';

import GrayDropDown from '../BasicFeeOptionModal/GrayDropDown';
import NewStyleModalFrame from '../NewStyleModalFrame';

import classNames from 'classnames/bind';
import style from './BillingStoragePackageModal.module.scss';

const cx = classNames.bind(style);

const BillingStoragePackageModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [packageName, setPackageName] = useState('');
  const [selectedSource, setSelectedSource] = useState(0);
  const [selectedSize, setSelectedSize] = useState(0);
  const [selectedStorage, setSelectedStorage] = useState({
    label: '',
    value: '',
  });
  const [storageList, setStorageList] = useState([]);
  const [size, setSize] = useState('');
  const [price, setPrice] = useState('');
  const [footerMessage, setFooterMessage] = useState('');

  const { submit, cancel, chargeType } = data;

  const newSubmit = {
    text: submit.text,
    func: async () => {},
  };

  const sourceList = [
    {
      label: 'On-premises',
      value: 0,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'NAVER CLOUD',
      value: 1,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'Azure',
      value: 2,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'AWS',
      value: 3,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const sizeList = [
    {
      label: 'GB',
      value: 0,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'MB',
      value: 1,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'KB',
      value: 2,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const handlePackageName = (e) => {
    setPackageName(e.target.value);
  };

  const handleSelectStorage = ({ label, value }) => {
    setSelectedStorage({ value, label });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedSource(Number(value));
  };

  const radioSizeBtnHandler = (name, value) => {
    setSelectedSize(Number(value));
  };

  const handleSize = (e) => {
    const inputValue = e.target.value;

    setSize(inputValue);
  };

  const formatPrice = (value) => {
    const onlyNumbers = value.replace(/[^0-9]/g, '');

    return onlyNumbers.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  };

  const handlePrice = (e) => {
    const inputValue = e.target.value;

    setPrice(formatPrice(inputValue));
  };

  const getStorageList = async () => {
    const response = await callApi({
      url: 'workspaces/option',
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      const list = result.storage_list.map(({ id, name }) => ({
        label: name,
        value: id,
      }));
      setStorageList([...list]);
    }
  };

  useEffect(() => {
    getStorageList();
  }, []);

  useEffect(() => {
    const messages = [
      {
        condition: !packageName,
        message: '패키지 이름을 입력해 주세요.',
      },
      {
        condition: !selectedStorage.label,
        message: '스토리지를 선택해 주세요.',
      },
      {
        condition: !size,
        message: '할당 용량을 입력해 주세요.',
      },
      {
        condition: !price,
        message: '월별 구독 요금을 입력해 주세요.',
      },
    ];

    const footerMessage =
      messages.find(({ condition }) => condition)?.message || '';

    setFooterMessage(footerMessage);
  }, [packageName, selectedStorage, size, price]);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={t('createChargePackage')}
      customStyle={{ maxHeight: '750px' }}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <InputBoxWithLabel
          labelText={t('packageName')}
          labelSize='large'
          disableErrorMsg
        >
          <InputText
            size='medium'
            name='packageName'
            value={packageName}
            placeholder={t('packageName.placeholder')}
            onChange={handlePackageName}
            // status={nameError ? 'error' : 'default'}
            // isReadOnly={readOnlyTxt === 'edit'}
            disableLeftIcon
            options={{ maxLength: 32 }}
            autoFocus
            tabIndex='1'
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('payPolicyOption')}
          labelSize='large'
          disableErrorMsg
        >
          <FbRadio
            name='source'
            options={sourceList}
            value={selectedSource}
            onChange={(e) => {
              radioBtnHandler('source', e.currentTarget.value);
            }}
            isLabelColor
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={`${t('storage')} ${t('select.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <GrayDropDown
            list={storageList}
            value={selectedStorage}
            handleSelectOption={handleSelectStorage}
            placeholder={t('스토리지를 선택하세요')}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('payPolicyOption')}
          labelSize='large'
          disableErrorMsg
        >
          <FbRadio
            name='size'
            options={sizeList}
            value={selectedSize}
            onChange={(e) => {
              radioSizeBtnHandler('size', e.currentTarget.value);
            }}
            isLabelColor
          />
        </InputBoxWithLabel>
        <div className={cx('price-container')}>
          {size.length > 0 && (
            <span className={cx('unit')}>{sizeList[selectedSize].label}</span>
          )}

          <input
            value={size}
            onChange={handleSize}
            type='number'
            className={cx('price-input', size.length && 'blue-border')}
            placeholder={`할당 용량을 설정해 주세요.`}
          />
        </div>
        <InputBoxWithLabel
          labelText={t('구독 요금 정책')}
          labelSize='large'
          disableErrorMsg
        >
          <div className={cx('price-container')}>
            {price.length > 0 && <span className={cx('unit')}>원</span>}
            <input
              value={price}
              onChange={handlePrice}
              type='text'
              className={cx('price-input', price.length && 'blue-border')}
              placeholder={`월별 구독 요금 정책을 설정해 주세요.`}
            />
          </div>
        </InputBoxWithLabel>
      </div>
    </NewStyleModalFrame>
  );
};

export default BillingStoragePackageModal;
