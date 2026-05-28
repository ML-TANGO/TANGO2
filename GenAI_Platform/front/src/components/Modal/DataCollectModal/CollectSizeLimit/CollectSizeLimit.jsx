import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { InputNumber } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import SelectBox from '@src/components/atoms/SelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import classNames from 'classnames/bind';
import style from '../DataCollectModal.module.scss';

const cx = classNames.bind(style);

export default function CollectSizeLimit({
  value,
  limitSizeValue,
  limitSizeUnit,
  handleSizeLimit,
  handleSizeLimitValue,
}) {
  const { t } = useTranslation();

  const options = useMemo(() => {
    return [
      {
        label: t('activation.label'),
        value: 1,
      },
      {
        label: t('deactivation.label'),
        value: 0,
      },
    ];
  }, [t]);

  const sizeOptions = useMemo(() => {
    return [
      {
        label: 'KB',
        value: 'KB',
      },
      {
        label: 'MB',
        value: 'MB',
      },
      {
        label: 'GB',
        value: 'GB',
      },
      {
        label: 'TB',
        value: 'TB',
      },
    ];
  }, []);

  return (
    <div className={cx('row')}>
      <InputBoxWithLabel
        labelText={t('collect.size.limit.label')}
        labelSize='large'
        disableErrorMsg
      >
        <Radio
          name='size-limit'
          value={value}
          options={options}
          onChange={handleSizeLimit}
          isLabelColor
        />
        {!!value && (
          <>
            <div className={cx('border')}></div>
            <div className={cx('flex-box')}>
              <InputNumber
                customSize={{ width: '269px', height: '38px', padding: '12px' }}
                valueAlign={'left'}
                value={limitSizeValue}
                placeholder='용량을 입력해 주세요.'
                onChange={(e) => {
                  handleSizeLimitValue('value', +e.target.value);
                }}
                disableIcon
              />
              <SelectBox
                list={sizeOptions}
                value={limitSizeUnit}
                style={{ height: '38px', width: '276px' }}
                placeholder='용량 단위 선택'
                handleOptionClick={(v) => handleSizeLimitValue('unit', v.value)}
              />
            </div>
          </>
        )}
      </InputBoxWithLabel>
    </div>
  );
}
