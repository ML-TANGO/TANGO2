// Atom

// Components

// i18n
import { useTranslation } from 'react-i18next';

import { Checkbox, InputNumber } from '@tango/ui-react';

import InstanceTooltip from '@src/components/organisms/InstanceTooltip';

// Colors
// import { colors } from '@src/utils/colors';

// CSS Module
import classNames from 'classnames/bind';
import style from './GpuListItem.module.scss';

const cx = classNames.bind(style);

const calMaxValue = (edit, free, inputValue) => {
  if (edit) {
    if (inputValue === undefined) {
      return free;
    }
    return free + inputValue;
  }

  return free;
};

function GpuListItem({
  listLength,
  idx,
  model,
  gpuName,
  total = 0,
  selected,
  ram,
  gpu,
  cpu,
  free,
  avail,
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

  const remainingSize = avail - inputValue;
  const maxValue = calMaxValue(edit, free, used);

  const calContentStyle = (idx, listLength) => {
    if (idx === 0) {
      return {
        top: 0,
        transform: 'translate(26px, 0)',
      };
    }

    if (idx + 1 === listLength && idx + 1 > 2) {
      return {
        top: '100%',
        transform: 'translate(26px, -100%)',
      };
    }

    return {
      top: '50%',
      transform: 'translate(26px, -50%)',
    };
  };

  return (
    <li key={idx}>
      <div
        className={cx('list-item', `${maxValue}` === '0' && 'test')}
        style={customStyle}
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
                contentsCustomStyle={calContentStyle(idx, listLength)}
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
            <div className={cx('sub-row')}>{total} EA</div>
            {type.includes('WORKSPACE') || type.includes('WORKER') ? (
              <div className={cx('sub-row')}>{remainingSize} EA</div>
            ) : (
              ''
            )}
          </>
        )}
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
          customSize={{ width: '100%' }}
        />
      </div>
    </li>
  );
}

export default GpuListItem;
