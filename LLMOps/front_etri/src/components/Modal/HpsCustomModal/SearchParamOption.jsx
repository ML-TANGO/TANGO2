import React from 'react';
import { useTranslation } from 'react-i18next';

import { InputNumber, InputText } from '@tango/ui-react';

import FbRadio from '@src/components/atoms/input/Radio';

import classNames from 'classnames/bind';
import style from './SearchParamOption.module.scss';

const cx = classNames.bind(style);

const accessOption = [
  {
    label: 'Int',
    value: 0,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
  {
    label: 'Float',
    value: 1,
    labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
  },
];

const SearchParamOption = ({
  id,
  name,
  max,
  min,
  count,
  type,
  handleParamInfo,
  deleteParamInfo,
  isLast,
}) => {
  const { t } = useTranslation();

  return (
    <div className={cx('container', isLast && 'last')}>
      <div className={cx('first-box')}>
        <InputText
          placeholder={t('파라미터 이름을 입력하세요')}
          onChange={(e) => {
            handleParamInfo({ id, info: 'name', value: e.target.value });
          }}
          name='name'
          value={name}
          options={{ maxLength: 50 }}
          autoFocus={false}
          customStyle={{ fontSize: '14px', width: '304px' }}
          disableLeftIcon
          disableClearBtn
        />
        <FbRadio
          name={`accessType${id}`}
          options={accessOption}
          value={type}
          onChange={(e) => {
            handleParamInfo({
              id,
              info: 'type',
              value: Number(e.target.value),
            });
          }}
          isLabelColor
        />
      </div>
      <div className={cx('second-box')}>
        <InputText
          placeholder={t('min.label')}
          onChange={(e) => {
            handleParamInfo({ id, info: 'min', value: e.target.value });
          }}
          name='min'
          value={min}
          options={{ maxLength: 50 }}
          autoFocus={false}
          customStyle={{ fontSize: '14px', width: '144px' }}
          disableLeftIcon
          disableClearBtn
        />
        <InputText
          placeholder={`${t('max.label')}`}
          onChange={(e) => {
            handleParamInfo({ id, info: 'max', value: e.target.value });
          }}
          name='max'
          value={max}
          options={{ maxLength: 50 }}
          autoFocus={false}
          customStyle={{ fontSize: '14px', width: '144px' }}
          disableLeftIcon
          disableClearBtn
        />
        <InputText
          placeholder={`${t('search.label')} ${t('count.label')}`}
          onChange={(e) => {
            handleParamInfo({ id, info: 'count', value: e.target.value });
          }}
          name='count'
          value={count}
          options={{ maxLength: 50 }}
          autoFocus={false}
          customStyle={{ fontSize: '14px', width: '144px' }}
          disableLeftIcon
          disableClearBtn
        />
        <img
          width={20}
          height={20}
          src='/images/icon/00-ic-new-delete.svg'
          alt='delete'
          className={cx('icon')}
          onClick={() => deleteParamInfo(id)}
        />
      </div>
    </div>
  );
};

export default SearchParamOption;
