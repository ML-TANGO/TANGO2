import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@tango/ui-react';

import { callApi, STATUS_SUCCESS } from '@src/network';

import BlueSelectCheckIcon from './blue-check.svg';
import ModelIcon from './model-icon.svg';

import classNames from 'classnames/bind';
import style from './TangoModelSearch.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import info from '@src/static/images/icon/00-ic-gray-info.svg';

const cx = classNames.bind(style);

const TangoModelSearch = ({
  selectCategory,
  setSelectCategory,
  selectModel,
  setSelectModel,
  ...rest
}) => {
  const { t } = useTranslation();
  // const [selectCategory, setSelectCategory] = useState({ name: '', value: '' });
  // const [selectModel, setSelectModel] = useState({ name: '', value: '' });
  const [categoryList, setCategoryList] = useState([]);
  const [modelList, setModelList] = useState([]);
  const [isCategoryOpen, setIsCategoryOpen] = useState(false);
  const [isModelOpen, setIsModelOpen] = useState(false);
  const [modelInput, setModelInput] = useState('');

  const handleCategory = (val) => {
    setSelectCategory({ name: val, value: val });
    setSelectModel({ name: '', value: '' });
    setIsCategoryOpen((prev) => !prev);
    setIsModelOpen(true);
    fetchModel(val);
  };

  const fetchCategory = async () => {
    const response = await callApi({
      url: 'options/built-in-model/category',
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setCategoryList(result.map((v) => ({ name: v, value: v })));
    }
  };

  const fetchModel = async (name) => {
    const response = await callApi({
      url: `options/built-in-model/category/models?category=${name}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setModelList(result.map(({ name }) => ({ name, value: name })));
    }
  };

  useEffect(() => {
    fetchCategory();
  }, []);

  // useEffect(() => {
  //   fetchModel();
  // }, [fetchModel]);

  return (
    <div className={cx('container')} {...rest}>
      <div
        className={cx('header')}
        onClick={() => setIsCategoryOpen((prev) => !prev)}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('category.label')}</span>
          {selectCategory.name && (
            <span className={cx('text')}>{selectCategory.name}</span>
          )}
          {!selectCategory.name && (
            <span className={cx('place-holder')}>
              {t('categorySelect.error.message')}
            </span>
          )}
        </div>
        <img src={isCategoryOpen ? arrowUp : arrowDown} alt='arrow' />
      </div>
      {isCategoryOpen && (
        <div className={cx('content-box')}>
          <div className={cx('data-box')}>
            {categoryList.map(({ name }, index) => (
              <div
                className={cx('data-content')}
                key={index}
                onClick={() => {
                  handleCategory(name);
                }}
              >
                <div className={cx('left-side')}>
                  <img
                    src={BlueSelectCheckIcon}
                    width={16}
                    height={16}
                    alt='icon'
                  />
                  <span>{name}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div
        className={cx('header', 'data', !isModelOpen && 'close')}
        onClick={() => setIsModelOpen((prev) => !prev)}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('model.label')}</span>
          {selectModel.name && (
            <span className={cx('text')}>
              {selectModel.name.length < 50
                ? selectModel.name
                : `${selectModel.name.slice(0, 50)}...`}
            </span>
          )}
          {!selectModel.name && (
            <span className={cx('place-holder')}>
              {t('modelSelect.message')}
            </span>
          )}
        </div>
        <img src={isModelOpen ? arrowUp : arrowDown} alt='arrow' />
      </div>
      {isModelOpen && (
        <div className={cx('content-box', 'data', isModelOpen && 'open')}>
          <div className={cx('data-search-box')}>
            <div className={cx('input')}>
              <InputText
                value={modelInput}
                onChange={(e) => {
                  setModelInput(e.target.value);
                }}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                customStyle={{ height: '32px' }}
              />
            </div>
          </div>
          <div className={cx('data-box')}>
            {modelList.map(({ name }, index) => (
              <div
                className={cx(
                  'data-content',
                  name === selectModel.name && 'selected',
                )}
                onClick={() => {
                  setSelectModel({ name, value: name });
                }}
                key={index}
              >
                <div
                  className={cx(
                    'left-side',
                    name === selectModel.name && 'selected',
                  )}
                >
                  <img src={ModelIcon} width={16} height={16} alt='icon' />
                  <span>
                    {name.length < 40 ? name : `${name.slice(0, 40)}...`}
                  </span>
                  <img src={info} alt='info' width={16} height={16} />
                  {name === selectModel.name && (
                    <img
                      src={BlueSelectCheckIcon}
                      width={16}
                      height={16}
                      alt='check'
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TangoModelSearch;
