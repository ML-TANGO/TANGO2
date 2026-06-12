import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { InputNumber } from '@tango/ui-react';

import SelectBox from '@src/components/atoms/SelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS Module
import classNames from 'classnames/bind';
import style from './CollectCycle.module.scss';

const cx = classNames.bind(style);

export default function CollectCycle({
  cycleValue,
  cycleUnit,
  handleCollectCycle,
}) {
  const options = useMemo(() => {
    return [
      {
        value: 'hour',
        label: '시간',
      },
      {
        value: 'day',
        label: '일',
      },
      {
        value: 'week',
        label: '주',
      },

      {
        value: 'month',
        label: '월',
      },
    ];
  }, []);

  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={'수집 주기'}
        labelSize='large'
        disableErrorMsg
      >
        <div className={cx('flex-box')}>
          <InputNumber
            name='cycleValue'
            customSize={{ width: '269px', height: '38px', padding: '12px' }}
            valueAlign={'left'}
            value={cycleValue}
            placeholder='주기를 입력해 주세요.'
            onChange={(e) =>
              handleCollectCycle({ name: 'value', value: +e.target.value })
            }
            disableIcon
          />
          <SelectBox
            name='cycleUnit'
            placeholder='주기 단위 선택'
            list={options}
            value={cycleUnit}
            style={{ height: '38px', width: '276px' }}
            handleOptionClick={(v) =>
              handleCollectCycle({ name: 'unit', value: v.value })
            }
          />
        </div>
      </InputBoxWithLabel>
    </div>
  );
}
