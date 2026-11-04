import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import FbRadio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { closeModal } from '@src/store/modules/modal';

import { callApi, STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';
import GrayDropDown from './GrayDropDown';
import OutBoundForm from './OutBoundForm';

import classNames from 'classnames/bind';
import style from './BasicFeeOptionModal.module.scss';

const cx = classNames.bind(style);

const TIME_UNIT = ['second', 'minute', 'hour', 'month'];

const BasicFeeOptionModal = ({ data, type }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [selectedTimePolicy, setSelectedTimePolicy] = useState(0);
  const [basicPrice, setBasicPrice] = useState('');
  const [addPrice, setAddPrice] = useState('');
  const [selectedPersonCount, setSelectedPersonCount] = useState({
    value: '',
    label: '',
  });
  const [boundId, setBoundId] = useState(1);

  const [outBoundOption, setOutBoundOption] = useState([
    { start: '', startUnit: '', end: '', endUnit: '', cost: '', id: 1 },
  ]);
  const [validate, setValidate] = useState(false);
  const [footerMessage, setFooterMessage] = useState('');

  const basicPersonlist = [
    { value: 1, label: '1명' },
    { value: 5, label: '5명' },
    { value: 10, label: '10명' },
    { value: 50, label: '50명' },
    { value: 100, label: '100명' },
    { value: 200, label: '200명' },
  ];

  const formatPrice = (value) => {
    // 숫자 값만 필터링 (숫자가 아닌 경우 제거)
    const onlyNumbers = value.replace(/[^0-9]/g, '');
    // 천 단위 콤마 추가
    return onlyNumbers.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  };

  const handleBasicPriceChange = (e) => {
    const inputValue = e.target.value;

    setBasicPrice(formatPrice(inputValue));
  };

  const handleAddPriceChange = (e) => {
    const inputValue = e.target.value;

    setAddPrice(formatPrice(inputValue));
  };

  const handleSelectedPersonCount = ({ label, value }) => {
    setSelectedPersonCount({ value, label });
  };

  const radioBtnHandler = (name, value) => {
    setSelectedTimePolicy(Number(value));
  };

  const handleOutBoundOption = ({ id, type, value }) => {
    setOutBoundOption((prevOptions) =>
      prevOptions.map((option) =>
        option.id === id
          ? {
              ...option,
              [type]: type === 'cost' ? formatPrice(value) : value,
            }
          : option,
      ),
    );
  };

  const deleteOutBoundOption = (id) => {
    setOutBoundOption((prevOptions) =>
      prevOptions.filter((option) => option.id !== id),
    );
  };

  const addOutBoundOption = () => {
    setOutBoundOption((prevOptions) => [
      ...prevOptions,
      {
        start: '',
        startUnit: '',
        end: '',
        endUnit: '',
        cost: '',
        id: boundId + 1,
      },
    ]);
    setBoundId((prev) => prev + 1);
  };

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
    {
      label: 'perMonth',
      value: 3,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const { submit, cancel } = data;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const body = {
        time_unit: TIME_UNIT[selectedTimePolicy],
        time_unit_cost: Number(basicPrice),
        members: Number(selectedPersonCount.value),
        add_member_cost: Number(addPrice),
        out_bound_network: outBoundOption.map(
          ({ start, startUnit, end, endUnit, cost }) => ({
            start: Number(start),
            start_unit: startUnit,
            end: Number(end),
            end_unit: endUnit,
            cost: Number(cost),
          }),
        ),
      };

      const response = await callApi({
        url: 'cost-management/basic-cost',
        method: 'post',
        body,
      });

      const { status } = response;

      if (status === STATUS_SUCCESS) {
        dispatch(closeModal('BASIC_FEE_OPTION'));
      }
    },
  };

  useEffect(() => {
    const isValidOutBound = outBoundOption.every(
      ({ start, startUnit, end, endUnit, cost }) =>
        start && startUnit && end && endUnit && cost,
    );

    if (
      !basicPrice ||
      !addPrice ||
      !selectedPersonCount.value ||
      !isValidOutBound
    ) {
      setValidate(false);
      return;
    }

    setValidate(true);
  }, [basicPrice, addPrice, selectedPersonCount, outBoundOption]);

  useEffect(() => {
    const messages = [
      {
        condition: !basicPrice,
        message: `${t(
          timePolicy[selectedTimePolicy].label,
        )} 기본 요금 정책을 입력해 주세요.`,
      },
      {
        condition: !selectedPersonCount.label,
        message: '기본 구성원 수를 선택해주세요',
      },
      {
        condition: !addPrice,
        message: '구성원 추가 요금을 입력해 주세요.',
      },
      {
        condition: !outBoundOption.every(
          ({ start, startUnit, end, endUnit, cost }) =>
            start && startUnit && end && endUnit && cost,
        ),
        message: '구간 요금을 입력해 주세요.',
      },
    ];

    const footerMessage =
      messages.find(({ condition }) => condition)?.message || '';

    setFooterMessage(footerMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    basicPrice,
    addPrice,
    selectedPersonCount,
    outBoundOption,
    selectedTimePolicy,
  ]);

  return (
    <NewStyleModalFrame
      submit={newSubmit}
      cancel={cancel}
      isResize={true}
      isMinimize={true}
      type={type}
      title={t('basicBillingOption')}
      validate={validate}
      customStyle={{ maxHeight: '750px' }}
      footerMessage={footerMessage}
    >
      <div className={cx('row')}>
        <span className={cx('workspace-header')}>
          {t('workspaceFeeOption')}
        </span>
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
          {basicPrice.length > 0 && <span className={cx('unit')}>원</span>}

          <input
            value={basicPrice}
            onChange={handleBasicPriceChange}
            type='text'
            className={cx('price-input', basicPrice && 'isEntered')}
            placeholder={`${t(
              timePolicy[selectedTimePolicy].label,
            )} 사용 요금 정책을 설정해 주세요.`}
          />
        </div>
        <InputBoxWithLabel
          labelText={`${t('basicMemberCount')} ${t('set.label')}`}
          labelSize='large'
          disableErrorMsg
        >
          <GrayDropDown
            list={basicPersonlist}
            value={selectedPersonCount}
            handleSelectOption={handleSelectedPersonCount}
            placeholder={t('basic.person.placeholder')}
          />
        </InputBoxWithLabel>
        <InputBoxWithLabel
          labelText={t('add.person.option')}
          labelSize='large'
          disableErrorMsg
        >
          <div className={cx('price-container')}>
            {addPrice.length > 0 && <span className={cx('unit')}>원</span>}

            <input
              value={addPrice}
              onChange={handleAddPriceChange}
              type='text'
              className={cx('price-input', addPrice && 'isEntered')}
              placeholder={t('addPrice.desc')}
            />
          </div>
        </InputBoxWithLabel>
        <div className={cx('gray-middle-line')}></div>
        <div className={cx('bound-container')}>
          <div className={cx('bound-header')}>
            <span className={cx('bound-title')}>
              {t('setupOutBoundNetwork')}
            </span>
            <span className={cx('add-btn')} onClick={addOutBoundOption}>
              {`${t('section.label')} ${t('add.label')}`}
            </span>
          </div>
          <div className={cx('bound-form-container')}>
            {outBoundOption.map(
              ({ start, startUnit, end, endUnit, id, cost }) => (
                <div key={id}>
                  <OutBoundForm
                    start={start}
                    startUnit={startUnit}
                    end={end}
                    endUnit={endUnit}
                    id={id}
                    cost={cost}
                    deleteOutBoundOption={deleteOutBoundOption}
                    handleOutBoundOption={handleOutBoundOption}
                  />
                  <div
                    className={cx(
                      'option-line',
                      id === outBoundOption[outBoundOption.length - 1].id &&
                        'last',
                    )}
                  ></div>
                </div>
              ),
            )}
          </div>
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default BasicFeeOptionModal;
