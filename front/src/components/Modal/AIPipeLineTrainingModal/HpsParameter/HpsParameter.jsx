import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import FixParamOption from '../../HpsCustomModal/FixParamOption';
import SearchParamOption from '../../HpsCustomModal/SearchParamOption';

// CSS Module
import classNames from 'classnames/bind';
import style from './HpsParameter.module.scss';

const cx = classNames.bind(style);

export default function HpsParameter({
  fixParam,
  handleFixParamInfo,
  deleteFixParam,
  addFixParam,
  searchParam,
  handleParamInfo,
  deleteParamInfo,
  addSearchParam,
}) {
  const { t } = useTranslation();

  return (
    <InputBoxWithLabel
      labelText={`${t('검색 파라미터 설정')}`}
      labelSize='large'
      disableErrorMsg
      style={{ marginBottom: '32px' }}
    >
      <div className={cx('search-param-box')}>
        <div className={cx('range-param')}>
          <span className={cx('header-text')}>고정 파라미터</span>
          {fixParam.map(({ name, id, param }, index) => (
            <FixParamOption
              key={id}
              name={name}
              id={id}
              param={param}
              handleFixParamInfo={handleFixParamInfo}
              deleteFixParam={deleteFixParam}
              isLast={index === fixParam.length - 1}
            />
          ))}

          <div className={cx('add-btn', 'bottom-line')}>
            <span>+</span>
            <span onClick={addFixParam}>고정파라미터 추가</span>
          </div>
          <span className={cx('header-text')}>범위 파라미터</span>
          {searchParam.map(({ id, name, max, min, count, type }, index) => (
            <SearchParamOption
              key={id}
              id={id}
              name={name}
              max={max}
              min={min}
              count={count}
              type={type}
              handleParamInfo={handleParamInfo}
              deleteParamInfo={deleteParamInfo}
              isLast={index === searchParam.length - 1}
            />
          ))}
          <div className={cx('add-btn')} onClick={addSearchParam}>
            <span>+</span>
            <span>파라미터 추가</span>
          </div>
        </div>
      </div>
    </InputBoxWithLabel>
  );
}
