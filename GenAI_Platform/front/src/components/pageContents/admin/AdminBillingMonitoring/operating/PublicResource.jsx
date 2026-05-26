import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import GrayDropDown from '@src/components/Modal/BasicFeeOptionModal/GrayDropDown';

import classNames from 'classnames/bind';
import style from './PublicResource.module.scss';

const cx = classNames.bind(style);

const PublicResource = () => {
  const { t } = useTranslation();

  const [resourceList, setResourceList] = useState([]);
  const [selectedCloud, setSelectedCloud] = useState({ label: '', value: '' });
  const [selectedResource, setSelectedResource] = useState({
    label: '',
    value: '',
  });

  const cloudList = [
    { value: 'onPremises', label: 'On-premises' },
    { value: 'naverCloud', label: 'NAVER CLOUD' },
    { value: 'azure', label: 'Azure' },
    { value: 'aws', label: 'AWS' },
  ];

  const handleSelectedCloud = ({ label, value }) => {
    setSelectedCloud({ value, label });
  };

  const handleSelectedResource = ({ label, value }) => {
    setSelectedResource({ value, label });
  };

  return (
    <div className={cx('workspace-usage-graph-box')}>
      <div className={cx('header')}>
        <div className={cx('left-content')}>
          <span className={cx('title')}>
            동일 사양 자원 퍼블릭 클라우드별 누적 운영 비용 비교
          </span>
        </div>
        <div className={cx('right-content')}>
          <span className={cx('text')}>{t('filter.label')}</span>
          <GrayDropDown
            list={cloudList}
            value={selectedCloud}
            placeholder={t('resource.compare.label')}
            handleSelectOption={handleSelectedCloud}
            customStyle={{ width: '160px' }}
            isCloseBorder={false}
          />
          <GrayDropDown
            list={resourceList}
            value={selectedResource}
            placeholder={t('resource.label')}
            handleSelectOption={handleSelectedResource}
            customStyle={{ width: '160px' }}
            isCloseBorder={false}
          />
        </div>
      </div>
      <div className={cx('graph-container')}></div>
    </div>
  );
};

export default PublicResource;
