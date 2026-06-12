import { InputText } from '@tango/ui-react';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';
import BlueInstanceInfo from './BlueInstanceInfo';
import InstanceInfo from './InstanceInfo';
import searchIcon from '/images/icon/00-ic-gray-search.svg';
import downArrow from '/images/icon/ic-arrow-gray-down.svg';
import upArrow from '/images/icon/ic-arrow-gray-up.svg';

import classNames from 'classnames/bind';
import style from './BillingPackageModal.module.scss';

const cx = classNames.bind(style);
const TIME_UNIT = ['second', 'minute', 'hour'];

const BillingPackageModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [packageName, setPackageName] = useState('');
  const [isInstanceSelectOpen, setIsInstanceSelectOpen] = useState(false);
  const [instanceList, setInstanceList] = useState([]);
  const [searchInstanceList, setSearchInstanceList] = useState([]);
  const [instanceType, setInstanceType] = useState([
    { name: 'On-premises', checked: true },
    { name: 'NAVER CLOUD', checked: true },
    { name: 'AZURE', checked: true },
    { name: 'AWS', checked: true },
  ]);
  const [selectedTimePolicy, setSelectedTimePolicy] = useState(0);
  const [selectedInstance, setSelectedInstance] = useState([]);
  const [price, setPrice] = useState('');
  const [footerMessage, setFooterMessage] = useState('');

  const timePolicy = [
    {
      label: 'perSecond',
      value: 0,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'perMinute',
      value: 1,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
    {
      label: 'perHour',
      value: 2,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const { submit, cancel, chargeType } = data;
  // chargeType: payYou(종량제), subscribe(구독제)

  const newSubmit = {
    text: submit.text,
    func: async () => {
      const body = {
        name: packageName,
        time_unit: TIME_UNIT[selectedTimePolicy],
        time_unit_cost: Number(price),
        instance_list: selectedInstance.map(({ name, id }) => ({
          source: name,
          instance_id: id,
          instance_allocate: 0, // 어떤값을 보내야하는지 미정
        })),
        type: '', // 종량제 구독제에 따라서 보내는 값이 달라져야한다.
      };

      const response = await callApi({
        url: 'cost-management/instance-package',
        method: 'post',
        body,
      });

      const { status } = response;

      if (status === STATUS_SUCCESS) {
        dispatch(closeModal('BILLING_PACKAGE'));
      }
    },
  };

  const handleInstanceType = (name) => {
    setInstanceType((prevInstanceType) =>
      prevInstanceType.map((type) =>
        type.name === name ? { ...type, checked: !type.checked } : type,
      ),
    );
  };

  const formatPrice = (value) => {
    const onlyNumbers = value.replace(/[^0-9]/g, '');

    return onlyNumbers.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  };

  const handlePrice = (e) => {
    const inputValue = e.target.value;

    setPrice(formatPrice(inputValue));
  };

  const handlePackageName = (e) => {
    setPackageName(e.target.value);
  };

  const radioBtnHandler = (name, value) => {
    setSelectedTimePolicy(Number(value));
  };

  const handleSelectedInstance = (id) => {
    setSelectedInstance((prevSelected) => {
      if (prevSelected.some((instance) => instance.id === id)) {
        return prevSelected.filter((instance) => instance.id !== id);
      } else {
        const newInstance = instanceList.find((instance) => instance.id === id);
        return [...prevSelected, newInstance];
      }
    });
  };

  const handleSearchList = (value) => {
    if (value) {
      const list = instanceList.filter(({ name }) =>
        name.toLowerCase().includes(value),
      );
      setSearchInstanceList([...list]);
      return;
    }

    setSearchInstanceList([...instanceList]);
  };

  const getInstanceList = async () => {
    const response = await callApi({
      url: 'workspaces/option',
      method: 'get',
    });

    const { status, result } = response;

    if (status === STATUS_SUCCESS) {
      setInstanceList(result.instance_list);
      setSearchInstanceList(result.instance_list);
    }
  };

  useEffect(() => {
    getInstanceList();
  }, []);

  useEffect(() => {
    const messages = [
      {
        condition: !packageName,
        message: '패키지 이름을 입력해 주세요.',
      },
      {
        condition: !selectedInstance.length,
        message: '인스턴스를 선택해 주세요.',
      },
      {
        condition: !price && chargeType === 'payYou',
        message: `${t(
          timePolicy[selectedTimePolicy].label,
        )} 사용 요금을 입력해 주세요.`,
      },
      {
        condition: !price && chargeType === 'subscribe',
        message: '월별 구독 요금을 입력해 주세요.',
      },
    ];

    const footerMessage =
      messages.find(({ condition }) => condition)?.message || '';

    setFooterMessage(footerMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packageName, selectedInstance, selectedTimePolicy, price]);

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
          labelText={t('selectInstance.label')}
          labelSize='large'
          disableErrorMsg
        >
          {!isInstanceSelectOpen && (
            <div className={cx('instance-not-open')}>
              <div
                className={cx(
                  'header',
                  selectedInstance.length > 0 && 'selected',
                )}
                onClick={() => setIsInstanceSelectOpen((prev) => !prev)}
              >
                <span>
                  {selectedInstance.length === 0
                    ? '인스턴스를 선택하세요'
                    : '추가 인스턴스 선택'}
                </span>
                <img src={downArrow} alt='arrow' width={16} height={16} />
              </div>

              {selectedInstance.length > 0 && (
                <span className={cx('instance-box')}>
                  {selectedInstance.map(({ name, cpu, gpu, ram }, index) => (
                    <BlueInstanceInfo
                      key={index}
                      name={name}
                      cost={10000}
                      time_unit={'second'}
                      cpu={cpu}
                      gpu={gpu}
                      ram={ram}
                    />
                  ))}
                </span>
              )}
            </div>
          )}
          {isInstanceSelectOpen && (
            <div className={cx('instance-container')}>
              <div className={cx('type-select')}>
                <span className={cx('desc-text')}>출처</span>
                {instanceType.map(({ name, checked }) => (
                  <div className={cx('type-box')} key={name}>
                    <input
                      type='checkbox'
                      checked={checked}
                      onChange={() => handleInstanceType(name)}
                    />
                    <span className={cx(checked && 'checked')}>{name}</span>
                  </div>
                ))}
                <img
                  onClick={() => setIsInstanceSelectOpen((prev) => !prev)}
                  src={upArrow}
                  alt='arrow'
                />
              </div>
              <div className={cx('search-box')}>
                <img
                  className={cx('search-icon')}
                  src={searchIcon}
                  alt='icon'
                />
                <input
                  type='text'
                  className={cx('search-input')}
                  placeholder='이름, 설명'
                  onChange={(e) => handleSearchList(e.target.value)}
                />
              </div>
              <div className={cx('instance-list')}>
                {searchInstanceList.map(
                  ({ name, cpu, gpu, ram, id }, index) => (
                    <InstanceInfo
                      key={index}
                      name={name}
                      type={'임시 타입'}
                      cost={10000}
                      time_unit={'second'}
                      cpu={cpu}
                      gpu={gpu}
                      ram={ram}
                      id={id}
                      handleSelectedInstance={handleSelectedInstance}
                      selectedInstance={selectedInstance}
                    />
                  ),
                )}
              </div>
              <div className={cx('selected-instance-box')}>
                {selectedInstance.map(({ name, cpu, gpu, ram }, index) => (
                  <BlueInstanceInfo
                    key={index}
                    name={name}
                    cost={10000}
                    time_unit={'second'}
                    cpu={cpu}
                    gpu={gpu}
                    ram={ram}
                  />
                ))}
              </div>
            </div>
          )}
        </InputBoxWithLabel>
        {chargeType === 'payYou' && (
          <>
            <InputBoxWithLabel
              labelText={t('payPolicyOption')}
              labelSize='large'
              disableErrorMsg
            >
              <FbRadio
                name='timePolicy'
                options={timePolicy}
                value={selectedTimePolicy}
                onChange={(e) => {
                  radioBtnHandler('timePolicy', e.currentTarget.value);
                }}
                isLabelColor
              />
            </InputBoxWithLabel>
            <div className={cx('price-container')}>
              {price.length > 0 && <span className={cx('unit')}>원</span>}

              <input
                value={price}
                onChange={handlePrice}
                type='text'
                className={cx('price-input')}
                placeholder={`${t(
                  timePolicy[selectedTimePolicy].label,
                )} 사용 요금 정책을 설정해 주세요.`}
              />
            </div>
          </>
        )}
        {chargeType === 'subscribe' && (
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
                className={cx('price-input')}
                placeholder={`월별 구독 요금 정책을 설정해 주세요.`}
              />
            </div>
          </InputBoxWithLabel>
        )}
      </div>
    </NewStyleModalFrame>
  );
};

export default BillingPackageModal;
