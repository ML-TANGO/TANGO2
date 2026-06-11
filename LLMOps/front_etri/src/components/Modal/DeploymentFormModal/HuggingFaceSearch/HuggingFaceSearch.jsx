import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { InputText } from '@tango/ui-react';

import SubMenuItem from '@src/components/Modal/FineTuningDataUploadModal/SearchComponent/Item/SubMenuItem';

import { closeModal, openModal } from '@src/store/modules/modal';
import { callApi, STATUS_SUCCESS } from '@src/network';

import BlueSelectCheckIcon from './blue-check.svg';
import BubbleTip from './bubble-tip.svg';
import HuggingIcon from './hugging-icon.svg';

import classNames from 'classnames/bind';
import style from './HuggingFaceSearch.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import info from '@src/static/images/icon/00-ic-gray-info.svg';

const cx = classNames.bind(style);

const defaultMenuOption = [
  { label: 'Public', value: 'public' },
  { label: 'Private', value: 'private' },
];

const HuggingFaceSearch = ({
  selectCategory,
  setSelectCategory,
  selectModel,
  setSelectModel,
  ...rest
}) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  // const [selectCategory, setSelectCategory] = useState({ name: '', value: '' });
  // const [selectModel, setSelectModel] = useState({ name: '', url: '' });
  const [categoryList, setCategoryList] = useState([]);
  const [modelList, setModelList] = useState([]);
  const [isCategoryOpen, setIsCategoryOpen] = useState(false);
  const [isModelOpen, setIsModelOpen] = useState(false);
  const [token, setToken] = useState('');
  const [keyword, setKeyword] = useState('');
  const [scope, setScope] = useState({
    label: 'Public',
    value: 'public',
  });

  const [visibleToolTip, setVisibleToolTip] = useState('');

  const showTooltip = (url) => {
    setVisibleToolTip(url);
  };

  const hideTooltip = () => {
    setVisibleToolTip('');
  };

  const fetchCategory = async () => {
    const response = await callApi({
      url: 'options/model-categories',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setCategoryList(result.map((value) => ({ name: value, value })));
    }
  };

  const fetchModel = async () => {
    const body = {
      model_name: keyword,
      huggingface_token: token,
      private: scope.value === 'public' ? 0 : 1,
      task: selectCategory.value,
    };

    const response = await callApi({
      method: 'post',
      url: 'options/huggingface-models',
      body,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setModelList(result.map(({ id, url }) => ({ name: id, url })));
    }
  };

  const handleCategory = ({ name }) => {
    setSelectCategory({ name, value: name });
    setIsCategoryOpen(false);
    setIsModelOpen(true);
  };

  const handleModel = ({ name, url }) => {
    setSelectModel({ name, url });
  };

  const openTokenModal = async () => {
    dispatch(
      openModal({
        modalType: 'HUGGINGFACE_TOKEN_MODAL',
        modalData: {
          onSubmit: (token) => {
            setToken(token);
            setScope({ label: 'Private', value: 'private' });
            dispatch(closeModal('HUGGINGFACE_TOKEN_MODAL'));
          },
          postHuggingFace: fetchModel,
        },
      }),
    );
  };

  const handleScope = (e) => {
    const { value } = e;
    if (value === 'private') {
      openTokenModal();
    } else {
      setScope(e);
    }
  };

  useEffect(() => {
    fetchCategory();
  }, []);

  useEffect(() => {
    fetchModel();
  }, [keyword, token, scope, selectCategory]);

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
                  handleCategory({ name });
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
                value={keyword}
                onChange={(e) => {
                  setKeyword(e.target.value);
                }}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                customStyle={{ height: '32px' }}
              />
            </div>
            <div className={cx('owner-box')}>
              <span className={cx('text')}>{t('owner.label')}</span>
              <SubMenuItem
                option={defaultMenuOption}
                select={scope}
                onChangeHandler={(e) => handleScope(e)}
                customStyle={{
                  marginBottom: 0,
                  marginRight: 0,
                }}
                labelHeight={{}}
                size={'xsmall'}
              />
            </div>
          </div>
          <div className={cx('data-box')}>
            {modelList.map(({ name, owner = '', url }, index) => (
              <div
                className={cx(
                  'data-content',
                  name === selectModel.name && 'selected',
                )}
                onClick={() => {
                  handleModel({ name, url });
                }}
                key={index}
              >
                <div
                  className={cx(
                    'left-side',
                    name === selectModel.name && 'selected',
                  )}
                >
                  <img src={HuggingIcon} width={16} height={16} alt='icon' />
                  <span>
                    {name.length < 40 ? name : `${name.slice(0, 40)}...`}
                  </span>
                  <div className={cx('info-icon')}>
                    <img
                      src={info}
                      width={16}
                      height={16}
                      alt='icon'
                      data-text={url}
                      onMouseEnter={() => showTooltip(url)}
                      onMouseLeave={hideTooltip}
                      className={cx('icon')}
                    />
                    {visibleToolTip === url && (
                      <>
                        <img src={BubbleTip} className={cx('tip')} alt='' />
                        <span className={cx('url')}>{url}</span>
                      </>
                    )}
                  </div>

                  {name === selectModel.name && (
                    <img
                      src={BlueSelectCheckIcon}
                      width={16}
                      height={16}
                      alt='check'
                    />
                  )}
                </div>
                <span
                  className={cx(
                    'user',
                    name === selectModel.name && 'selected',
                  )}
                >
                  {owner}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default HuggingFaceSearch;
