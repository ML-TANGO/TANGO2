import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

import FbRadio from '@src/components/atoms/input/Radio';
import GrayDropDown from '@src/components/Modal/BasicFeeOptionModal/GrayDropDown';

import classNames from 'classnames/bind';
import style from './WorkspaceInfo.module.scss';

const cx = classNames.bind(style);

const WorkspaceInfo = () => {
  const { t } = useTranslation();

  const [periodType, setPeriodType] = useState(0);
  const [selectedCloud, setSelectedCloud] = useState({ label: '', value: '' });
  const [selectedResource, setSelectedResource] = useState({
    label: '',
    value: '',
  });

  const periodList = [
    {
      label: '일별',
      value: 0,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: '주별',
      value: 1,
      labelStyle: {
        fontSize: '14px',
        fontFamily: 'SpoqaM',
        marginRight: '16px',
      },
    },
    {
      label: '월별',
      value: 2,
      labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
    },
  ];

  const cloudList = [
    { value: 'onPremises', label: 'On-premises' },
    { value: 'naverCloud', label: 'NAVER CLOUD' },
    { value: 'azure', label: 'Azure' },
    { value: 'aws', label: 'AWS' },
  ];

  const resourceList = [
    { value: 'totalResource', label: '전체 자원' },
    { value: 'totalInstance', label: '전체 인스턴스' },
    { value: 'totalStorage', label: '전체 스토리지' },
  ];

  const periodRadioBtnHandler = (name, value) => {
    setPeriodType(Number(value));
  };

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
          <span className={cx('title')}>워크스페이스별 자원 사용 현황</span>
          <div className={cx('option-box')}>
            <FbRadio
              name='periodType'
              options={periodList}
              value={periodType}
              onChange={(e) => {
                periodRadioBtnHandler('periodType', e.currentTarget.value);
              }}
              isLabelColor
            />
          </div>
        </div>
        <div className={cx('right-content')}>
          <span className={cx('text')}>{t('filter.label')}</span>
          <GrayDropDown
            list={[]}
            value={{ label: '', value: '' }}
            placeholder={t('selectWorkspace.placeholder')}
            handleSelectOption={() => {}}
            customStyle={{ width: '160px' }}
            isCloseBorder={false}
          />
          <GrayDropDown
            list={cloudList}
            value={selectedCloud}
            placeholder={t('출처')}
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

export default WorkspaceInfo;
