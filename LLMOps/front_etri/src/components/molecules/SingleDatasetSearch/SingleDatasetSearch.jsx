import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';

import { InputText } from '@tango/ui-react';

import SubMenuItem from '@src/components/Modal/FineTuningDataUploadModal/SearchComponent/Item/SubMenuItem';

import { callApi, STATUS_SUCCESS } from '@src/network';

import classNames from 'classnames/bind';
import style from './SingleDatasetSearch.module.scss';

import arrowDown from '@src/static/images/icon/00-ic-basic-arrow-02-down-grey.svg';
import arrowUp from '@src/static/images/icon/00-ic-basic-arrow-02-up-grey.svg';
import BlueSelectCheckIcon from '@src/static/images/icon/dataset/blue-check.svg';
import DataFileIcon from '@src/static/images/icon/dataset/data-file.svg';
import DataFolderIcon from '@src/static/images/icon/dataset/data-folder.svg';
import LeftArrowIcon from '@src/static/images/icon/dataset/left-arrow.svg';

const cx = classNames.bind(style);

const defaultMenuOption = [
  { label: 'total.label', value: 'total' },
  { label: 'me.label', value: 'me' },
];

const SingleDatasetSearch = ({
  workspaceId,
  selectData,
  setSelectedData,
  canFileSelect = true,
}) => {
  const { t } = useTranslation();
  const { auth } = useSelector((state) => ({
    auth: state.auth,
  }));
  const { userName } = auth;

  const [isDataOpen, setIsDataOpen] = useState(false);

  const [dataOwner, setDataOwner] = useState({
    label: 'total.label',
    value: 'total',
  });
  const [showDataList, setShowDataList] = useState([]);
  const [currentDepth, setCurrentDepth] = useState(0);
  const [prevFolder, setPrevFolder] = useState([]);
  const [dataInput, setDataInput] = useState('');

  const onClickDataOwner = (e) => {
    setDataOwner(e);
  };

  const fetchData = async () => {
    const path = prevFolder.join('/');
    const response = await callApi({
      url: `options/data?workspace_id=${workspaceId}&path=${path}`,
    });

    const { result, status } = response;

    if (status === STATUS_SUCCESS) {
      setShowDataList(result);
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

  useEffect(() => {
    fetchData();
  }, [prevFolder]);

  return (
    <div className={cx('container')}>
      <div
        className={cx('header', !isDataOpen && 'close')}
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
        <div className={cx('content-box')}>
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
            {currentDepth > 0 && (
              <div className={cx('data-content')} onClick={goToPrevDepth}>
                <div className={cx('left-side')}>
                  <img src={LeftArrowIcon} width={16} height={16} alt='icon' />
                  <span>{`.../`}</span>
                </div>
                <span className={cx('user')}>상위 폴더로 이동</span>
              </div>
            )}

            {showDataList
              .filter((v) =>
                v.name.includes(dataInput) && dataOwner.value === 'total'
                  ? true
                  : userName === v.owner,
              )
              .map(({ depth, full_path, name, owner, type }, index) => (
                <div
                  className={cx(
                    'data-content',
                    name === selectData.name && 'selected',
                    type === 'file' && !canFileSelect && 'file-disabled',
                  )}
                  onClick={() =>
                    handleData({ name, fullPath: full_path, type })
                  }
                  key={index}
                >
                  <div
                    className={cx(
                      'left-side',
                      name === selectData.name && 'selected',
                    )}
                  >
                    <img
                      src={type === 'file' ? DataFileIcon : DataFolderIcon}
                      width={16}
                      height={16}
                      alt='icon'
                    />
                    <span>
                      {name.length < 40 ? name : `${name.slice(0, 40)}...`}
                    </span>
                    {name === selectData.name && (
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
                      name === selectData.name && 'selected',
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

export default SingleDatasetSearch;
