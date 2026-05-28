// Atom

// Components
import { Checkbox, InputNumber } from '@jonathan/ui-react';

import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

// Colors
// import { colors } from '@src/utils/colors';

// CSS Module
import classNames from 'classnames/bind';
import style from './GpuListItem.module.scss';

const cx = classNames.bind(style);

function GpuListItem({
  idx,
  model,
  gpuName,
  total = 0,
  selected,
  ram,
  gpu,
  cpu,
  free,
  inputValue,
  edit,
  list,
  checkboxHandler,
  onChangeInputValue,
  type,
  isReadOnly,
  used,
  customStyle,
}) {
  const { t } = useTranslation();
  let remainingSize = free;

  const [maxValue, setMaxValue] = useState(0);

  useEffect(() => {
    let newMaxValue = edit ? free + used : free;

    // if (edit && selected && `${newMaxValue}` === `0`) {
    //   newMaxValue = inputValue;
    // }

    setMaxValue(newMaxValue);
  }, [edit, selected, free, maxValue]);

  return (
    <li key={idx}>
      <div
        style={customStyle}
        className={cx('list-item', `${maxValue}` === '0' && 'test')}
      >
        <div className={cx('check')}>
          <Checkbox
            value={idx}
            disabled={`${maxValue}` === '0'}
            // label={model}
            customLabelStyle={{
              padding: '0 0 0 3px',
              fontSize: '14px',
            }}
            name='gpuModel'
            checked={selected}
            // customStyle={{}}
            onChange={() => {
              checkboxHandler({ idx });
            }}
          />
          <div className={cx('instance-name-box')}>
            <div className={cx('model-name')}>{model}</div>

            <div className={cx('tooltip-box')}>
              <InstanceTooltip
                instanceType={gpuName ? 'GPU' : 'CPU'}
                gpuName={gpuName}
                gpuAllocateNum={gpu}
                cpuAllocateNum={cpu}
                ramAllocateNum={ram}
              />
            </div>
          </div>
        </div>
        {list && list.length > 0 ? (
          list.map((v) => {
            return <div className={cx('sub-row')}>{v}</div>;
          })
        ) : (
          <>
            <div className={cx('sub-row')}>
              {t('ea.label', { count: total })}
            </div>
            {type.includes('WORKSPACE') || type.includes('WORKER') ? (
              <div className={cx('sub-row')}>
                {t('ea.label', { count: remainingSize })}
              </div>
            ) : (
              ''
            )}
          </>
        )}

        {/* <div>{t('ea.label', { count: free })}</div> */}

        <InputNumber
          name='workspaceInput'
          placeholder={`${t('currentAvailableCount')} : ${
            maxValue === '' ? '0' : maxValue
          }`}
          min={0}
          max={maxValue}
          value={inputValue}
          onChange={(e) => {
            if (`${maxValue}` === '0') return;
            let inputValue = e.value;

            if (e.value > maxValue) {
              inputValue = maxValue;
            }
            onChangeInputValue({
              idx,
              value: inputValue,
            });
          }}
          isReadOnly={isReadOnly || `${maxValue}` === '0'}
          disabled={`${maxValue}` === '0'}
          // disableIcon={`${maxValue}` === '0'}
          // bottomTextExist={true}
        />
      </div>
    </li>
  );
}

export default GpuListItem;
