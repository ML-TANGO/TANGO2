import React from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@jonathan/ui-react';

import classNames from 'classnames/bind';
import style from './FixParamOption.module.scss';

const cx = classNames.bind(style);

const FixParamOption = ({
  id,
  name,
  param,
  handleFixParamInfo,
  isLast,
  deleteFixParam,
}) => {
  const { t } = useTranslation();
  return (
    <div className={cx('container', isLast && 'last')}>
      <InputText
        placeholder={t('파라미터 이름을 입력하세요')}
        onChange={(e) => {
          handleFixParamInfo({ id, info: 'name', value: e.target.value });
        }}
        name='name'
        value={name}
        options={{ maxLength: 50 }}
        autoFocus={false}
        customStyle={{ fontSize: '14px', width: '264px' }}
        disableLeftIcon
        disableClearBtn
      />
      <InputText
        placeholder={t('파라미터 값을 입력하세요')}
        onChange={(e) => {
          handleFixParamInfo({ id, info: 'param', value: e.target.value });
        }}
        name='param'
        value={param}
        options={{ maxLength: 50 }}
        autoFocus={false}
        customStyle={{ fontSize: '14px', width: '180px' }}
        disableLeftIcon
        disableClearBtn
      />
      <img
        width={20}
        height={20}
        src='/images/icon/00-ic-new-delete.svg'
        alt='delete'
        className={cx('icon')}
        onClick={() => deleteFixParam(id)}
      />
    </div>
  );
};

export default FixParamOption;
