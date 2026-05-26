import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import {
  useHistory,
  useLocation,
  useParams,
  useRouteMatch,
} from 'react-router-dom';

import { InputText } from '@jonathan/ui-react';

import _ from 'lodash';

import { callApi, STATUS_SUCCESS } from '@src/network';

import SubMenuItem from '../../FineTuningDataUploadModal/SearchComponent/Item/SubMenuItem';
import BlueSelectCheckIcon from './blue-check.svg';
import ModelIcon from './model-icon.svg';

import classNames from 'classnames/bind';
import style from './LoadTrainingSearch.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import info from '@src/static/images/icon/00-ic-gray-info.svg';
import GroupIcon from '@src/static/images/icon/00-ic-llm-group.svg';

const cx = classNames.bind(style);

const trainingMenuOption = [
  { label: 'total.label', value: 'total' },
  { label: 'me.label', value: 'me' },
];
const modelMenuOption = [
  { label: 'name.label', value: 'name' },
  { label: 'createdDate.label', value: 'createdDate' },
];

const LoadTrainingSearch = ({
  selectCategory,
  setSelectCategory,
  selectModel,
  setSelectModel,
  workspaceId,
  getTrainingUrl,
  editMode,
  ...rest
}) => {
  const { t } = useTranslation();
  // const [selectCategory, setSelectCategory] = useState({ name: '', value: '' });
  // const [selectModel, setSelectModel] = useState({ name: '', value: '' });
  const [originTrainingList, setOriginTrainingList] = useState([]);
  const [originModelList, setOriginModelList] = useState([]);
  const [trainingList, setTrainingList] = useState([]);
  const [modelList, setModelList] = useState([]);

  const [isCategoryOpen, setIsCategoryOpen] = useState(false);
  const [isModelOpen, setIsModelOpen] = useState(false);
  const [trainingInput, setTrainingInput] = useState('');
  const [modelInput, setModelInput] = useState('');

  const [trainingSubmenu, setTrainingSubmenu] = useState({
    name: 'total.label',
    value: 'total',
  });
  const [modelSubmenu, setModelSubmenu] = useState({
    label: 'name.label',
    value: 'name',
  });

  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));

  const { userName } = auth;

  const handleCategory = (val, id) => {
    setSelectCategory({ name: val, value: id });
    setSelectModel({ name: '', value: '' });
    setIsCategoryOpen((prev) => !prev);
    fetchModel(id);
    setIsModelOpen(true);
  };

  //* 첫번째
  const fetchCategory = useCallback(async () => {
    const url = getTrainingUrl + `?workspace_id=${workspaceId}`;
    const response = await callApi({
      url,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const resultList = result.map((v) => ({
        name: v.name,
        value: v.id,
        owner: v.owner,
        access: v.access,
      }));
      setTrainingList(resultList);
      setOriginTrainingList(resultList);
    }
  }, [getTrainingUrl, workspaceId]);

  // 두 번째 get
  const fetchModel = async (id) => {
    const response = await callApi({
      url: `options/project/training?project_id=${id}`,
      method: 'get',
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      const modelData = result.map((v) => ({
        name: v.name,
        value: v.id,
        projectId: v.project_id,
        type: v.type,
        startDatetime: v.start_datetime,
      }));
      setModelList(modelData);
      setOriginModelList(modelData);
    }
  };

  //* Submenu 선택
  const onClickSubMenu = async (selectedItem, type) => {
    if (type === 'first') {
      let newData = _.cloneDeep(originTrainingList);
      // 첫번째에서 - sort
      setTrainingInput(''); // input 초기화
      setTrainingSubmenu(selectedItem);

      if (selectedItem.value === 'me') {
        newData = newData.filter((item) => item.owner === userName);
      }
      setTrainingList(newData);
    } else {
      // 두번째에서 - sort
      setModelInput('');
      setModelSubmenu(selectedItem);
    }
  };

  //* 첫번째 input 핸들러러
  const firstInputHandler = (v) => {
    //
    let newData = _.cloneDeep(originTrainingList);
    if (trainingSubmenu.value === 'me') {
      // 내이름 따와야함 .. auth
      newData = newData.filter((item) => item.owner === userName);
    } else {
      // newData = newData.filter((item) => item.name.includes(v));
    }
    newData = newData.filter((item) => item.name.includes(v));

    setTrainingInput(v);
    setTrainingList(newData);
  };

  //* 두번째 input 핸들러러
  const secondInputHandler = (v) => {
    //

    // ! { label: 'name.label', value: 'name' },
    // ! { label: 'createdDate.label', value: 'createdDate' },

    let newData = _.cloneDeep(originModelList);
    if (v !== '') {
      if (modelSubmenu.value === 'name') {
        // 내이름 따와야함 .. auth
        newData = newData.filter((item) => item.name.includes(v));
      } else {
        newData = newData.filter((item) => item.startDatetime.includes(v));
      }
    }
    setModelInput(v);
    setModelList(newData);
  };

  useEffect(() => {
    fetchCategory();
  }, [fetchCategory]);

  return (
    <div className={cx('container')} {...rest}>
      <div
        className={cx('header', editMode && 'edit')}
        onClick={() => {
          if (!editMode) {
            setIsCategoryOpen((prev) => !prev);
          }
        }}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('training.label')}</span>
          {selectCategory.name && (
            <span className={cx('text')}>{selectCategory.name}</span>
          )}
          {!selectCategory.name && (
            <span className={cx('place-holder')}>
              {t('trainingSelect.error.message')}
            </span>
          )}
        </div>
        <img src={isCategoryOpen ? arrowUp : arrowDown} alt='arrow' />
      </div>
      {isCategoryOpen && (
        <div className={cx('content-box')}>
          <div className={cx('data-search-box')}>
            <div className={cx('input')}>
              <InputText
                value={trainingInput}
                onChange={(e) => {
                  firstInputHandler(e.target.value);
                }}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                customStyle={{ height: '32px' }}
              />
            </div>
            <div className={cx('button-box')}>
              <div className={cx('button')}>
                <span className={cx('type-title')}>{t('owner.label')}</span>
                <SubMenuItem
                  option={trainingMenuOption}
                  select={trainingSubmenu}
                  onChangeHandler={(e) => onClickSubMenu(e, 'first')}
                  customStyle={{
                    marginBottom: 0,
                    marginRight: 0,
                  }}
                  labelHeight={{}}
                  size={'xsmall'}
                />
              </div>
            </div>
          </div>
          <div className={cx('data-box')}>
            {trainingList.map(({ name, value, owner }) => (
              <div
                className={cx('data-content')}
                key={value}
                onClick={() => {
                  handleCategory(name, value);
                }}
              >
                <div className={cx('left-side')}>
                  <img src={GroupIcon} width={16} height={16} alt='icon' />
                  <span>{name}</span>
                </div>
                <div className={cx('right-side')}>{owner}</div>
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
          editMode && 'edit',
        )}
        onClick={() => {
          if (!editMode) {
            setIsModelOpen((prev) => !prev);
          }
        }}
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
                  secondInputHandler(e.target.value);
                }}
                disableLeftIcon={false}
                placeholder={t('name.label')}
                customStyle={{ height: '32px' }}
              />
            </div>
            <div className={cx('button-box')}>
              <div className={cx('button')}>
                <span className={cx('type-title')}>{t('sortBy.label')}</span>
                <SubMenuItem
                  option={modelMenuOption}
                  select={modelSubmenu}
                  onChangeHandler={(e) => onClickSubMenu(e, 'second')}
                  customStyle={{
                    marginBottom: 0,
                    marginRight: 0,
                  }}
                  labelHeight={{}}
                  size={'xsmall'}
                />
              </div>
            </div>
          </div>
          <div className={cx('data-box')}>
            {modelList?.map((listItem, index) => {
              const { name, id, type, startDatetime, value } = listItem;

              return (
                <div
                  className={cx(
                    'data-content',
                    // name === selectModel.name && 'selected',
                    value === selectModel.value && 'selected',
                  )}
                  onClick={() => {
                    setSelectModel(listItem);
                  }}
                  key={index}
                >
                  <div
                    className={cx(
                      'left-side',
                      // name === selectModel.name && 'selected',
                      value === selectModel.value && 'selected',
                    )}
                  >
                    {/* <img src={ModelIcon} width={16} height={16} alt='icon' /> */}
                    <img
                      src={`/src/static/images/icon/ic-${type}-training.svg`}
                      width={16}
                      height={16}
                      alt='icon'
                    />
                    <span>
                      {name.length < 40 ? name : `${name.slice(0, 40)}...`}
                    </span>
                    {/* <img src={info} alt='info' width={16} height={16} /> */}
                    {value === selectModel.value && (
                      <img
                        src={BlueSelectCheckIcon}
                        width={16}
                        height={16}
                        alt='check'
                      />
                    )}
                  </div>
                  <div className={cx('right-side')}>{startDatetime}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default LoadTrainingSearch;
