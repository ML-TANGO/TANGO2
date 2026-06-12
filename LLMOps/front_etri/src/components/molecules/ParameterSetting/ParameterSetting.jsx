import React from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@tango/ui-react';

import InputBoxWithLabel from '../InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './ParameterSetting.module.scss';

const cx = classNames.bind(style);

export default function ParameterSetting({ builtInParams, handleParams }) {
  const { t } = useTranslation();
  return (
    <InputBoxWithLabel
      labelText={t('파라미터 설정')}
      labelSize='large'
      optionalSize='medium'
      disableErrorMsg
      style={{ marginTop: '32px' }}
    >
      <div className={cx('parameter-box')}>
        <div className={cx('param-header')}>
          <div className={cx('desc-text')}>파라미터 항목명</div>
          <div className={cx('desc-text')}>파라미터 값</div>
        </div>
        <div className={cx('param-list')}>
          {builtInParams.length === 0 && (
            <div className={cx('empty-info')}>
              데이터를 추가하시면 해당 데이터 대한 파라미터가 표시됩니다.
            </div>
          )}
          {builtInParams.map(({ label, value }, index) => (
            <div className={cx('list-box')} key={index}>
              <div className={cx('label')}>{label}</div>
              <div className={cx('input')}>
                <InputText
                  placeholder={t('파라미터 값을 입력하세요')}
                  onChange={(e) => handleParams(label, e.target.value)}
                  name='workspace'
                  value={value}
                  status={
                    builtInParams[index].value === '' ? 'error' : 'default'
                  }
                  options={{ maxLength: 50 }}
                  customStyle={{ fontSize: '13px' }}
                  disableLeftIcon
                  disableClearBtn
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </InputBoxWithLabel>
  );
}
