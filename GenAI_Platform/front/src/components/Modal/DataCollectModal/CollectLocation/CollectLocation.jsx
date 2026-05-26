import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';

import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import DoubleDropdown from '../../ImportPromptModal/DoubleDropdown';

// CSS Module
import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

export const visiblityList = [
  { label: '전체', value: 0 },
  { label: '본인', value: 1 },
];

const calFilterList = (visibiltyValue, userName, list) => {
  if (visibiltyValue.value) {
    const filterMyList = list.filter((info) => info.name === userName);
    return filterMyList;
  }
  return list;
};

export default function CollectLocation({
  isFetching,
  folderListLoading = false,
  type = 'add',
  datasetValue,
  datasetList,
  folderValue,
  folderList,
  handleSelectedLocation,
}) {
  const { t } = useTranslation();
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const [isOpen, setIsOpen] = useState({
    firstIsOpen: type === 'edit' ? false : true,
    secondIsOpen: false,
  });

  const [datasetVisibility, setDatasetVisibility] = useState(visiblityList[0]);
  const [folderVisibility, setFolderVisibility] = useState(visiblityList[0]);

  const filterDatasetList = calFilterList(
    datasetVisibility,
    userName,
    datasetList,
  );
  const filterFolderList = calFilterList(
    folderVisibility,
    userName,
    folderList,
  );

  const handleDatasetVisibility = useCallback((value) => {
    setDatasetVisibility(value);
  }, []);
  const handleFolderVisibility = useCallback((value) => {
    setFolderVisibility(value);
  }, []);

  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={t('collect.location.label')}
        labelSize='large'
        disableErrorMsg
      >
        <DoubleDropdown
          isFetching={isFetching}
          icon={'/src/static/images/icon/dataset-black.svg'}
          isOpen={isOpen.firstIsOpen}
          handleIsOpen={(value) => {
            if (type === 'edit') return;
            setIsOpen((prev) => ({
              ...prev,
              firstIsOpen: value,
              secondIsOpen: !value,
            }));
          }}
          label={t('dataset.label')}
          placeholder={t('collect.dataset.placeholder')}
          options={filterDatasetList}
          value={datasetValue}
          handleSelected={(value) => {
            setIsOpen({
              firstIsOpen: false,
              secondIsOpen: true,
            });
            handleSelectedLocation('datasetValue', value);
            handleSelectedLocation('folderValue', {
              id: undefined,
              name: undefined,
            });
          }}
          visibilityLabel='생성자'
          visiblityList={visiblityList}
          visibilityValue={datasetVisibility}
          handleVisibility={handleDatasetVisibility}
          outerStyle={{
            backgroundColor: type === 'edit' && '#F0F0F0',
            borderRadius: '10px 10px 0 0',
            borderBottom: !isOpen.firstIsOpen && 'none',
          }}
          innerStyle={{ borderRadius: '0px', borderBottom: 'none' }}
        />
        <DoubleDropdown
          isFetching={folderListLoading}
          icon={'/src/static/images/icon/folder.svg'}
          isOpen={isOpen.secondIsOpen}
          handleIsOpen={(value) => {
            if (type === 'edit') return;
            setIsOpen((prev) => ({
              ...prev,
              firstIsOpen: false,
              secondIsOpen: value,
            }));
          }}
          label={t('collect.folder.label')}
          placeholder={t('collect.folder.placeholder')}
          options={filterFolderList}
          value={folderValue}
          handleSelected={(value) => {
            setIsOpen({
              firstIsOpen: false,
              secondIsOpen: false,
            });
            handleSelectedLocation('folderValue', value);
          }}
          visibilityLabel='생성자'
          visiblityList={visiblityList}
          visibilityValue={folderVisibility}
          handleVisibility={handleFolderVisibility}
          outerStyle={{
            backgroundColor: type === 'edit' && '#F0F0F0',
            borderRadius: `${isOpen.secondIsOpen ? '0px' : '0 0 10px 10px'}`,
          }}
          innerStyle={{ borderRadius: '0 0 10px 10px' }}
        />
      </InputBoxWithLabel>
    </div>
  );
}
