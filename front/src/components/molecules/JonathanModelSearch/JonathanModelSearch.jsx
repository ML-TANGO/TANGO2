import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { InputText } from '@jonathan/ui-react';

import { callApi, STATUS_SUCCESS } from '@src/network';

import BlueSelectCheckIcon from './blue-check.svg';
import EmpathyIcon from './empathy.svg';
import LanguageIcon from './language.svg';
import MedicalIcon from './medical.svg';
import ModelIcon from './model-icon.svg';
import VisualIcon from './visual.svg';

import classNames from 'classnames/bind';
import style from './JonathanModelSearch.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import info from '@src/static/images/icon/00-ic-gray-info.svg';

const cx = classNames.bind(style);

const JonathanModelSearch = ({
  selectCategory,
  setSelectCategory,
  selectModel,
  setSelectModel,
  disabled,
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
    setModelInput('');
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

  const fetchModel = async () => {
    const response = await callApi({
      url: `options/built-in-model/category/models`,
      method: 'get',
      params: {
        category: selectCategory.name,
      },
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setModelList(
        result.map(({ name, huggingface_model_id }) => ({
          name,
          value: huggingface_model_id,
        })),
      );
    }
  };

  const handleCategoryIcon = (value) => {
    if (value.includes('의료')) return MedicalIcon;
    if (value.includes('공감')) return EmpathyIcon;
    if (value.includes('자연어 이해') || value.includes('대화 생성'))
      return LanguageIcon;
    if (value.includes('시각')) return VisualIcon;

    return EmpathyIcon;
  };

  useEffect(() => {
    fetchCategory();
  }, []);

  useEffect(() => {
    fetchModel();
  }, [selectCategory]);

  return (
    <div className={cx('container')} {...rest}>
      <div
        className={cx('header', disabled && 'disabled')}
        onClick={() => {
          if (disabled) return;
          setIsCategoryOpen((prev) => !prev);
        }}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('category.label')}</span>
          {selectCategory.name && (
            <span className={cx('text', disabled && 'disabled')}>
              {selectCategory.name}
            </span>
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
                    src={handleCategoryIcon(name)}
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
        className={cx(
          'header',
          'data',
          !isModelOpen && 'close',
          disabled && 'disabled',
        )}
        onClick={() => {
          if (disabled) return;
          setIsModelOpen((prev) => !prev);
        }}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('model.label')}</span>
          {selectModel.name && (
            <span className={cx('text', disabled && 'disabled')}>
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
            {modelList
              .filter((v) => v.name.includes(modelInput))
              .map(({ name, value }, index) => (
                <div
                  className={cx(
                    'data-content',
                    name === selectModel.name && 'selected',
                  )}
                  onClick={() => {
                    setSelectModel({ name, value });
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

export default JonathanModelSearch;
