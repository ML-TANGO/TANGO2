import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useSelector } from 'react-redux';

import { Tooltip } from '@jonathan/ui-react';

import Dropdown from '@src/components/atoms/Dropdown';
import Radio from '@src/components/atoms/input/Radio';

import InputBoxWithLabel from '../InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './AccessOwnerSelect.module.scss';

const cx = classNames.bind(style);

export default function AccessOwnerSelect({
  isAccess = 1,
  tooltipContents,
  handleInputs,
  ownerValue,
  ownerList = [],
  handleOwner,
}) {
  const { t } = useTranslation();

  const accessOption = useMemo(() => {
    return [
      {
        label: 'public',
        value: 1,
        labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
      },
      {
        label: 'private',
        value: 0,
        labelStyle: { fontSize: '14px', fontFamily: 'SpoqaM' },
      },
    ];
  }, []);

  return (
    <div className={cx('cont')}>
      <InputBoxWithLabel
        labelText={t('accessType.label')}
        labelSize='large'
        labelDescText={
          tooltipContents && (
            <Tooltip
              icon='/src/static/images/icon/00-ic-alert-info-o.svg'
              iconCustomStyle={{
                width: '16px',
                height: '16px',
                marginLeft: '8px',
                paddingBottom: '2px',
              }}
              contents={tooltipContents}
              contentsAlign={{ vertical: 'top' }}
              contentsCustomStyle={{
                width: '300px',
                padding: '24px',
                borderRadius: '10px',
                border: '0.5px solid #DEE9FF',
                background: '#FFF',
                boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
              }}
            />
          )
        }
        disableErrorMsg
      >
        <Radio
          name='isAccess'
          value={isAccess}
          options={accessOption}
          onChange={handleInputs}
          customStyle={{ marginTop: '16px' }}
          isLabelColor
        />
      </InputBoxWithLabel>
      <InputBoxWithLabel
        labelText={t('owner.label')}
        labelSize='large'
        disableErrorMsg
      >
        <Dropdown
          list={ownerList}
          value={ownerValue}
          handleOptionClick={handleOwner}
          style={{ height: '38px' }}
          // disabled={ownerList.label !== userName}
        />
      </InputBoxWithLabel>
    </div>
  );
}
