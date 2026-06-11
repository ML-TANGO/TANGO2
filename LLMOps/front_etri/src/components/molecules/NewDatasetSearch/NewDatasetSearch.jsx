import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { FixedSizeList as List } from 'react-window';

import { InputText } from '@tango/ui-react';

import Loading from '@src/components/atoms/loading/Loading';
import SubMenuItem from '@src/components/Modal/FineTuningDataUploadModal/SearchComponent/Item/SubMenuItem';

import { callApi, STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './NewDatasetSearch.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import BlueSelectCheckIcon from '@src/static/images/icon/dataset/blue-check.svg';
import DataFileIcon from '@src/static/images/icon/dataset/data-file.svg';
import DataFolderIcon from '@src/static/images/icon/dataset/data-folder.svg';
import DatasetFolderIcon from '@src/static/images/icon/dataset/dataset-folder.svg';
import LeftArrowIcon from '@src/static/images/icon/dataset/left-arrow.svg';

const cx = classNames.bind(style);

const defaultMenuOption = [
  { label: 'total.label', value: 'total' },
  { label: 'me.label', value: 'me' },
];

const NewDatasetSearch = ({
  workspaceId,
  selectDataset,
  setSelectedDataset,
  selectData,
  setSelectedData,
  firstDisabled = false,
  canFileSelect = true,
}) => {
  const { t } = useTranslation();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));
  const { userName } = auth;

  const [datasetList, setDatasetList] = useState([]);
  const [isDatasetOpen, setIsDatasetOpen] = useState(false);
  const [isDataOpen, setIsDataOpen] = useState(false);
  const [datasetOwner, setDatasetOwner] = useState({
    label: 'total.label',
    value: 'total',
  });
  const [dataOwner, setDataOwner] = useState({
    label: 'total.label',
    value: 'total',
  });
  const [showDataList, setShowDataList] = useState([]);
  const [currentDepth, setCurrentDepth] = useState(0);
  const [prevFolder, setPrevFolder] = useState([]);
  const [datasetInput, setDatasetInput] = useState('');
  const [dataInput, setDataInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleDatasetClick = ({ id, name }) => {
    setSelectedDataset({ id, name });
    setIsDatasetOpen(false);
    setIsDataOpen(true);
  };

  const onClickDatasetOwner = (e) => {
    setDatasetOwner(e);
  };

  const onClickDataOwner = (e) => {
    setDataOwner(e);
  };

  const fetchDataset = async () => {
    const response = await callApi({
      url: `options/preprocessing/dataset?workspace_id=${workspaceId}`,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setDatasetList(result);
    }
  };

  const fetchData = async () => {
    if (!selectDataset.id) return;
    setIsLoading(true);

    const path = prevFolder.join('/');
    const response = await callApi({
      url: `options/data?dataset_id=${selectDataset.id}&workspace_id=${workspaceId}&path=${path}`,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setShowDataList(result);
      setIsLoading(false);
    }
  };

  const handleData = ({ name, fullPath, type }) => {
    if (type === 'file') {
      if (canFileSelect) setSelectedData({ name, fullPath });
      // setIsDataOpen(false);
      return;
    }

    setDataInput('');
    setSelectedData({ name, fullPath });
    setCurrentDepth((prev) => prev + 1);
    setPrevFolder((prev) => [...prev, name]);
  };

  const goToPrevDepth = () => {
    setCurrentDepth((prev) => prev - 1);
    setPrevFolder((prev) => prev.slice(0, -1));
    setDataInput('');
  };

  // 데이터셋 리스트 첫 랜더링에서 가져옴
  useEffect(() => {
    fetchDataset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 데이터셋이 갱신될때마다 값 전부 초기화 후 데이터 가져옴
  useEffect(() => {
    if (!selectDataset.id) return;
    setCurrentDepth((prev) => 0);
    setPrevFolder((prev) => []);
    setSelectedData({ name: '', fullPath: '' });

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectDataset]);

  // 폴더 선택하거나 상위폴더이동 누르면 data 갱신
  useEffect(() => {
    fetchData();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prevFolder]);

  const datasetColmn = ({ index, data, style }) => {
    if (data.length === 0) return;

    const { id, name, owner } = data[index];
    return (
      <div style={style}>
        <div
          className={cx('data-content')}
          key={id}
          onClick={() => handleDatasetClick({ id, name })}
        >
          <div className={cx('left-side')}>
            <img src={DatasetFolderIcon} width={16} height={16} alt='icon' />
            <span>{name}</span>
          </div>
          <span className={cx('user')}>{owner}</span>
        </div>
      </div>
    );
  };

  const Column = ({ index, data, style }) => {
    if (data.length === 0) return;
    const { name, owner, full_path, type } = data[index];

    return (
      <div style={style}>
        <div
          className={cx(
            'data-content',
            name === selectData.name && 'selected',
            type === 'file' && !canFileSelect && 'file-disabled',
          )}
          onClick={() => handleData({ name, fullPath: full_path, type })}
          key={index}
        >
          <div
            className={cx('left-side', name === selectData.name && 'selected')}
          >
            <img
              src={type === 'file' ? DataFileIcon : DataFolderIcon}
              width={16}
              height={16}
              alt='icon'
            />
            <span>{name.length < 40 ? name : `${name.slice(0, 40)}...`}</span>
            {name === selectData.name && (
              <img
                src={BlueSelectCheckIcon}
                width={16}
                height={16}
                alt='check'
              />
            )}
          </div>
          <span className={cx('user', name === selectData.name && 'selected')}>
            {owner}
          </span>
        </div>
      </div>
    );
  };

  const datasetFilterList = datasetList.filter((v) =>
    v.name.includes(datasetInput) && datasetOwner.value === 'total'
      ? true
      : userName === v.owner,
  );

  const filterDataList = showDataList.filter((v) =>
    v.name.includes(dataInput) && dataOwner.value === 'total'
      ? true
      : userName === v.owner,
  );

  return (
    <div className={cx('container')}>
      <div
        className={cx('header', firstDisabled && 'disabled')}
        onClick={() => {
          if (firstDisabled) return;
          setIsDatasetOpen((prev) => !prev);
        }}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('dataset')}</span>
          {selectDataset.name && (
            <span className={cx('text')}>{selectDataset.name}</span>
          )}
          {!selectDataset.name && (
            <span className={cx('place-holder')}>
              {t('graphDataset.message')}
            </span>
          )}
        </div>
        <img src={isDatasetOpen ? arrowUp : arrowDown} alt='arrow' />
      </div>
      {isDatasetOpen && (
        <div className={cx('content-box')}>
          <div className={cx('data-search-box')}>
            <div className={cx('input')}>
              <InputText
                value={datasetInput}
                onChange={(e) => {
                  setDatasetInput(e.target.value);
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
                select={datasetOwner}
                onChangeHandler={(e) => onClickDatasetOwner(e, 'first')}
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
            {!isLoading && (
              <List
                width={542}
                height={184}
                itemCount={datasetFilterList.length}
                itemSize={46}
                itemData={datasetFilterList}
                overscanCount={100}
                useIsScrolling
              >
                {datasetColmn}
              </List>
            )}
          </div>
        </div>
      )}
      <div
        className={cx('header', 'data', !isDataOpen && 'close')}
        onClick={() => setIsDataOpen((prev) => !prev)}
      >
        <div className={cx('left-side')}>
          <span className={cx('type')}>{t('data.label')}</span>
          {selectData.name && (
            <span className={cx('text')}>
              {selectData.name.length < 50
                ? selectData.name
                : `${selectData.name.slice(0, 50)}...`}
            </span>
          )}
          {!selectData.name && (
            <span className={cx('place-holder')}>{t('graphData.message')}</span>
          )}
        </div>
        <img src={isDataOpen ? arrowUp : arrowDown} alt='arrow' />
      </div>
      {isDataOpen && (
        <div className={cx('content-box', 'data', isDataOpen && 'open')}>
          <div className={cx('data-search-box')}>
            <div className={cx('input')}>
              <InputText
                value={dataInput}
                onChange={(e) => {
                  setDataInput(e.target.value);
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
                select={dataOwner}
                onChangeHandler={(e) => onClickDataOwner(e, 'second')}
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
            {!isLoading && currentDepth > 0 && (
              <div
                className={cx('data-content', 'back')}
                onClick={goToPrevDepth}
              >
                <div className={cx('left-side')}>
                  <img src={LeftArrowIcon} width={16} height={16} alt='icon' />
                  <span>{`.../`}</span>
                </div>
                <span className={cx('user')}>상위 폴더로 이동</span>
              </div>
            )}
            {isLoading && <Loading />}
            {!isLoading && (
              <List
                width={542}
                height={184}
                itemCount={filterDataList.length}
                itemSize={46}
                itemData={filterDataList}
                overscanCount={100}
                useIsScrolling
              >
                {Column}
              </List>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NewDatasetSearch;
